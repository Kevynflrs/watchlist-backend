import pandas as pd

from app.features import NUMERIC_FEATURES, fit_feature_bundle


def _sample_catalogue() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "genres": [
                "['Action', 'Drama']",
                "['Comedy']",
                "['Action', 'Comedy']",
            ],
            "average_rating": [7.5, 6.0, 8.0],
            "num_votes": [1000, 200, 5000],
            "year": [2010, 2015, 2020],
            "runtime": [120, 95, 110],
            "revenue": [1_000_000, 0, 50_000_000],
        }
    )


def test_fit_feature_bundle_returns_bundle_and_features():
    df = _sample_catalogue()

    bundle, df_features = fit_feature_bundle(df)

    # 3 genres distincts (Action, Comedy, Drama) + 5 colonnes numériques
    assert df_features.shape == (3, 3 + len(NUMERIC_FEATURES))
    assert set(bundle.mlb.classes_) == {"Action", "Comedy", "Drama"}


def test_numeric_features_are_scaled_between_zero_and_one():
    df = _sample_catalogue()

    _, df_features = fit_feature_bundle(df)

    for col in NUMERIC_FEATURES:
        assert df_features[col].min() >= 0
        assert df_features[col].max() <= 1


def test_transform_on_new_data_matches_training_columns():
    df = _sample_catalogue()
    bundle, df_features = fit_feature_bundle(df)

    new_movie = pd.DataFrame(
        {
            "genres": ["['Drama']"],
            "average_rating": [7.0],
            "num_votes": [300],
            "year": [2018],
            "runtime": [100],
            "revenue": [2_000_000],
        }
    )

    new_features = bundle.transform(new_movie)

    # Même nombre de colonnes, dans le même ordre, que l'entraînement
    assert list(new_features.columns) == list(df_features.columns)


def test_transform_ignores_unknown_genre_without_crashing():
    df = _sample_catalogue()
    bundle, _ = fit_feature_bundle(df)

    new_movie = pd.DataFrame(
        {
            "genres": ["['Horror']"],  # genre jamais vu au fit
            "average_rating": [5.0],
            "num_votes": [100],
            "year": [2022],
            "runtime": [90],
            "revenue": [0],
        }
    )

    # Ne doit pas lever d'exception, "Horror" est simplement ignoré
    result = bundle.transform(new_movie)
    assert result.shape[0] == 1
