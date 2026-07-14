from dataclasses import dataclass, field

import pandas as pd
from sklearn.preprocessing import MinMaxScaler, MultiLabelBinarizer

from app.ml_core import clean_genres

NUMERIC_FEATURES = [
    "average_rating",
    "num_votes",
    "year",
    "runtime",
    "revenue",
]  # Colonnes numériques utilisées comme features, scalées entre 0 et 1.


@dataclass
class FeatureBundle:
    """Encapsule les transformateurs déjà entraînés (fit), réutilisables via .transform()."""

    mlb: MultiLabelBinarizer
    scaler: MinMaxScaler
    numeric_features: list[str] = field(default_factory=lambda: list(NUMERIC_FEATURES))

    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        """Applique l'encodage genres + scaling numérique déjà appris, sans réentraîner."""
        df = df.copy()
        df["genres_list"] = df["genres"].apply(clean_genres)

        # .transform() (pas .fit_transform()) : réutilise les genres déjà connus du mlb entraîné.
        # Un genre jamais vu à l'entraînement est simplement ignoré (comportement par défaut du mlb).
        genres_encoded = self.mlb.transform(df["genres_list"])
        genres_df = pd.DataFrame(genres_encoded, columns=self.mlb.classes_, index=df.index)

        numeric_df = df[self.numeric_features].fillna(0)
        numeric_scaled = self.scaler.transform(numeric_df)
        numeric_scaled_df = pd.DataFrame(
            numeric_scaled, columns=self.numeric_features, index=df.index
        )

        return pd.concat([genres_df, numeric_scaled_df], axis=1)


def fit_feature_bundle(df: pd.DataFrame) -> tuple[FeatureBundle, pd.DataFrame]:
    """Entraîne le MultiLabelBinarizer et le MinMaxScaler sur le catalogue, une seule fois."""
    df = df.copy()
    df["genres_list"] = df["genres"].apply(clean_genres)

    mlb = MultiLabelBinarizer()
    genres_encoded = mlb.fit_transform(df["genres_list"])
    genres_df = pd.DataFrame(genres_encoded, columns=mlb.classes_, index=df.index)

    numeric_df = df[NUMERIC_FEATURES].fillna(0)
    scaler = MinMaxScaler()
    numeric_scaled = scaler.fit_transform(numeric_df)
    numeric_scaled_df = pd.DataFrame(numeric_scaled, columns=NUMERIC_FEATURES, index=df.index)

    bundle = FeatureBundle(mlb=mlb, scaler=scaler)
    df_features = pd.concat([genres_df, numeric_scaled_df], axis=1)

    return bundle, df_features
