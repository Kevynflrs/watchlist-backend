import numpy as np
import pandas as pd

from app.train import ModelBundle, train_model


def _fake_catalogue(n: int = 40) -> pd.DataFrame:
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


def test_train_model_returns_bundle_with_metrics():
    catalogue_df = _fake_catalogue()
    watched_df = _fake_watched(catalogue_df)

    bundle = train_model(catalogue_df, watched_df)

    assert isinstance(bundle, ModelBundle)
    assert 0.0 <= bundle.metrics["accuracy"] <= 1.0
    assert 0.0 <= bundle.metrics["roc_auc"] <= 1.0
    assert bundle.metrics["n_train"] + bundle.metrics["n_test"] == len(catalogue_df)


def test_save_and_load_bundle_gives_identical_predictions(tmp_path):
    catalogue_df = _fake_catalogue()
    watched_df = _fake_watched(catalogue_df)
    bundle = train_model(catalogue_df, watched_df)

    features_sample = bundle.feature_bundle.transform(catalogue_df.head(5))
    predictions_before = bundle.model.predict_proba(features_sample)[:, 1]

    save_path = tmp_path / "model_bundle.joblib"
    bundle.save(save_path)
    reloaded_bundle = ModelBundle.load(save_path)

    predictions_after = reloaded_bundle.model.predict_proba(features_sample)[:, 1]

    np.testing.assert_array_equal(predictions_before, predictions_after)
