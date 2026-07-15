from dataclasses import dataclass
from pathlib import Path
from typing import Any

import joblib
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, roc_auc_score
from sklearn.model_selection import train_test_split

from app.features import FeatureBundle, fit_feature_bundle
from app.ml_core import make_match_key

# Seuil au-dessus duquel un film est considéré "aimé" (label = 1).
RATING_THRESHOLD = 3.5


@dataclass
class ModelBundle:
    """Regroupe le modèle entraîné, le feature bundle associé, et les métriques d'entraînement."""

    model: RandomForestClassifier
    feature_bundle: FeatureBundle
    metrics: dict[str, Any]

    def save(self, path: Path) -> None:
        """Sérialise le bundle complet sur disque via joblib."""
        joblib.dump(self, path)

    @staticmethod
    def load(path: Path) -> "ModelBundle":
        """Recharge un bundle précédemment sauvegardé, prêt à prédire sans réentraînement."""
        return joblib.load(path)


def train_model(catalogue_df: pd.DataFrame, watched_df: pd.DataFrame) -> ModelBundle:
    """Entraîne le RandomForest à partir du catalogue et des films notés, retourne le bundle."""
    catalogue_df = catalogue_df.copy()
    watched_df = watched_df.copy()

    # Construit la clé de jointure des deux côtés, garantissant un format identique.
    catalogue_df["match_key"] = catalogue_df.apply(
        lambda row: make_match_key(row["title"], row["year"]), axis=1
    )
    watched_df["match_key"] = watched_df.apply(
        lambda row: make_match_key(row["title"], row["year"]), axis=1
    )

    # On n'entraîne que sur les films à la fois dans le catalogue ET notés (rating non-null).
    rated = watched_df.dropna(subset=["rating"])
    merged = catalogue_df.merge(rated[["match_key", "rating"]], on="match_key", how="inner")

    feature_bundle, features_df = fit_feature_bundle(merged)
    labels = (merged["rating"] >= RATING_THRESHOLD).astype(int)

    x_train, x_test, y_train, y_test = train_test_split(
        features_df, labels, test_size=0.2, stratify=labels, random_state=42
    )

    model = RandomForestClassifier(random_state=42)
    model.fit(x_train, y_train)

    y_pred = model.predict(x_test)
    y_proba = model.predict_proba(x_test)[:, 1]

    metrics = {
        "accuracy": accuracy_score(y_test, y_pred),
        "roc_auc": roc_auc_score(y_test, y_proba),
        "n_train": len(x_train),
        "n_test": len(x_test),
    }

    return ModelBundle(model=model, feature_bundle=feature_bundle, metrics=metrics)
