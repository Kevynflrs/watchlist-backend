import numpy as np
import pandas as pd

from app.ml_core import make_match_key
from app.scoring import categorize, score_catalogue
from app.train import train_model


def _fake_catalogue(n: int = 30) -> pd.DataFrame:
    rng = np.random.default_rng(42)
    genres_options = ["['Action']", "['Comedy']", "['Drama']", "['Action', 'Drama']"]
    return pd.DataFrame(
        {
            "title": [f"Movie {i}" for i in range(n)],
            "year": rng.integers(1990, 2024, n),
            "genres": rng.choice(genres_options, n),
            "average_rating": rng.uniform(4, 9, n),
            "num_votes": rng.integers(10, 5000, n),
            "runtime": rng.integers(80, 160, n),
            "revenue": rng.uniform(0, 100_000_000, n),
            "popularity": rng.uniform(1, 100, n),
        }
    )


def _fake_watched(catalogue_df: pd.DataFrame) -> pd.DataFrame:
    rng = np.random.default_rng(42)
    return pd.DataFrame(
        {
            "title": catalogue_df["title"],
            "year": catalogue_df["year"],
            "rating": rng.choice([1.0, 2.0, 3.0, 3.5, 4.0, 4.5, 5.0], len(catalogue_df)),
        }
    )


def test_categorize_blockbuster():
    row = pd.Series({"popularity": 80, "num_votes": 100})
    assert categorize(row) == "Blockbuster"


def test_categorize_grand_public():
    row = pd.Series({"popularity": 10, "num_votes": 1000})
    assert categorize(row) == "Grand Public"


def test_categorize_auteur():
    row = pd.Series({"popularity": 5, "num_votes": 50})
    assert categorize(row) == "Auteur"


def test_categorize_handles_missing_values():
    row = pd.Series({"popularity": None, "num_votes": None})
    assert categorize(row) == "Auteur"


def test_score_catalogue_excludes_watched_movies():
    catalogue_df = _fake_catalogue()
    watched_df = _fake_watched(catalogue_df)
    model_bundle = train_model(catalogue_df, watched_df)

    # On marque les 5 premiers films du catalogue comme "vus"
    watched_keys = {
        make_match_key(row["title"], row["year"]) for _, row in catalogue_df.head(5).iterrows()
    }

    result = score_catalogue(catalogue_df, watched_keys, model_bundle)

    result_keys = set(result["match_key"])
    assert result_keys.isdisjoint(watched_keys)


def test_score_catalogue_adds_expected_columns():
    catalogue_df = _fake_catalogue()
    watched_df = _fake_watched(catalogue_df)
    model_bundle = train_model(catalogue_df, watched_df)

    result = score_catalogue(catalogue_df, set(), model_bundle)

    assert "score_prediction" in result.columns
    assert "categorie_style" in result.columns
    assert result["score_prediction"].between(0, 1).all()
    assert set(result["categorie_style"]).issubset({"Blockbuster", "Grand Public", "Auteur"})
