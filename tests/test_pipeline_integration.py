import numpy as np
import pandas as pd

from app.features import fit_feature_bundle
from app.ml_core import make_match_key, prepare_catalogue
from app.scoring import score_catalogue
from app.train import ModelBundle, train_model


def _fake_raw_catalogue(n: int = 20) -> pd.DataFrame:
    """Simule un catalogue TMDB brut, avant nettoyage (avec un statut et une date à parser)."""
    rng = np.random.default_rng(42)
    genres_options = ["['Action']", "['Comedy']", "['Drama']", "['Action', 'Drama']"]
    statuses = rng.choice(["Released", "Post Production"], n, p=[0.9, 0.1])
    years = rng.integers(1990, 2024, n)

    return pd.DataFrame(
        {
            "title": [f"Movie {i}" for i in range(n)],
            "status": statuses,
            "release_date": [f"{year}-06-15" for year in years],
            "genres": rng.choice(genres_options, n),
            "average_rating": rng.uniform(4, 9, n),
            "num_votes": rng.integers(10, 5000, n),
            "runtime": rng.integers(80, 160, n),
            "revenue": rng.uniform(0, 100_000_000, n),
            "popularity": rng.uniform(1, 100, n),
        }
    )


def _fake_ratings(catalogue_df: pd.DataFrame) -> pd.DataFrame:
    """Simule un ratings.csv Letterboxd, couvrant seulement une partie du catalogue."""
    rng = np.random.default_rng(42)
    rated_subset = catalogue_df.sample(frac=0.7, random_state=42)
    return pd.DataFrame(
        {
            "title": rated_subset["title"].values,
            "year": rated_subset["year"].values,
            "rating": rng.choice([1.0, 2.0, 3.0, 3.5, 4.0, 4.5, 5.0], len(rated_subset)),
        }
    )


def test_full_pipeline_prepare_to_score():
    """Vérifie l'enchaînement complet : prepare -> fit_feature_bundle -> train_model -> score."""
    raw_catalogue = _fake_raw_catalogue()

    # Étape 1 : nettoyage du catalogue brut (filtre status, calcule year).
    clean_catalogue = prepare_catalogue(raw_catalogue)
    assert (clean_catalogue["status"] == "Released").all()
    assert "year" in clean_catalogue.columns

    # Étape 2 : ratings factices, couvrant une partie du catalogue nettoyé.
    ratings_df = _fake_ratings(clean_catalogue)

    # Étape 3 : feature engineering isolé (vérifie juste que ça ne plante pas en amont de train_model).
    feature_bundle, features_df = fit_feature_bundle(clean_catalogue)
    assert len(features_df) == len(clean_catalogue)

    # Étape 4 : entraînement réel du modèle sur catalogue nettoyé + ratings.
    model_bundle = train_model(clean_catalogue, ratings_df)
    assert isinstance(model_bundle, ModelBundle)
    assert 0.0 <= model_bundle.metrics["roc_auc"] <= 1.0

    # Étape 5 : scoring, avec quelques films marqués "vus" (non notés forcément).
    watched_keys = {
        make_match_key(row["title"], row["year"]) for _, row in clean_catalogue.head(3).iterrows()
    }
    scored_df = score_catalogue(clean_catalogue, watched_keys, model_bundle)

    assert set(scored_df["match_key"]).isdisjoint(watched_keys)
    assert "score_prediction" in scored_df.columns
    assert "categorie_style" in scored_df.columns


def test_reloaded_model_gives_same_scores(tmp_path):
    """Un ModelBundle rechargé depuis disque doit reproduire exactement les mêmes scores."""
    raw_catalogue = _fake_raw_catalogue()
    clean_catalogue = prepare_catalogue(raw_catalogue)
    ratings_df = _fake_ratings(clean_catalogue)

    model_bundle = train_model(clean_catalogue, ratings_df)

    scores_before = score_catalogue(clean_catalogue, set(), model_bundle)["score_prediction"]

    save_path = tmp_path / "model_bundle.joblib"
    model_bundle.save(save_path)
    reloaded_bundle = ModelBundle.load(save_path)

    scores_after = score_catalogue(clean_catalogue, set(), reloaded_bundle)["score_prediction"]

    np.testing.assert_array_equal(scores_before.values, scores_after.values)
