import pandas as pd

from app.ml_core import make_match_key
from app.train import ModelBundle

# Seuils de catégorisation, basés sur la popularité TMDB et le nombre de votes.
BLOCKBUSTER_MIN_POPULARITY = 50
GRAND_PUBLIC_MIN_VOTES = 500


def categorize(row: pd.Series) -> str:
    """Classe un film en 'Blockbuster', 'Grand Public' ou 'Auteur' selon popularité/nb de votes."""
    popularity = row.get("popularity") or 0
    num_votes = row.get("num_votes") or 0

    if popularity >= BLOCKBUSTER_MIN_POPULARITY:
        return "Blockbuster"
    if num_votes >= GRAND_PUBLIC_MIN_VOTES:
        return "Grand Public"
    return "Auteur"


def score_catalogue(
    catalogue_df: pd.DataFrame, watched_match_keys: set[str], model_bundle: ModelBundle
) -> pd.DataFrame:
    """Scorer les films non-vus du catalogue, avec score de prédiction et catégorie de style."""
    catalogue_df = catalogue_df.copy()
    catalogue_df["match_key"] = catalogue_df.apply(
        lambda row: make_match_key(row["title"], row["year"]), axis=1
    )

    # Exclusion des films déjà vus : la ligne la plus critique de toute cette fonction.
    unseen_df = catalogue_df[~catalogue_df["match_key"].isin(watched_match_keys)].reset_index(
        drop=True
    )

    features_df = model_bundle.feature_bundle.transform(unseen_df)
    scores = model_bundle.model.predict_proba(features_df)[:, 1]

    unseen_df["score_prediction"] = scores
    unseen_df["categorie_style"] = unseen_df.apply(categorize, axis=1)

    return unseen_df


def refresh_recommendation_scores(db, model_bundle) -> int:
    """Recalcule et persiste score_prediction/categorie_style pour tout le catalogue.

    Coûteux (transform + predict_proba sur tout le catalogue).
    """
    import pandas as pd

    catalogue_df = pd.read_sql("SELECT * FROM movies", con=db.get_bind())
    features_df = model_bundle.feature_bundle.transform(catalogue_df)
    scores = model_bundle.model.predict_proba(features_df)[:, 1]

    catalogue_df["score_prediction"] = scores
    catalogue_df["categorie_style"] = catalogue_df.apply(categorize, axis=1)

    # Mise à jour en masse via SQLAlchemy Core (bulk update), bien plus rapide que charger chaque objet ORM et faire un setattr un par un sur 100k lignes.
    from app.models_db import Movie

    updates = catalogue_df[["id", "score_prediction", "categorie_style"]].to_dict("records")
    db.bulk_update_mappings(Movie, updates)
    db.commit()

    return len(updates)
