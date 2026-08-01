import ast
import re

import pandas as pd

def make_match_key(title: str | None, year: int | float | None) -> str:
    """Construit une clé unique 'titre_annee' normalisée (minuscule, sans accents ni ponctuation)."""
    normalized_title = (title or "").strip().lower()
    normalized_title = re.sub(
        r"[^a-z0-9\s]", "", normalized_title
    )  # Supprime tout ce qui n'est pas lettre/chiffre/espace (ponctuation, apostrophes, ·, etc.)
    normalized_title = re.sub(
        r"\s+", " ", normalized_title
    ).strip()  # Réduit les espaces multiples à un seul, résultat de la suppression de ponctuation

    year_str = (
        "unknown" if pd.isna(year) else str(int(year))
    )  # pd.isna gère à la fois None et NaN (float), les deux cas rencontrés selon la source

    return f"{normalized_title}_{year_str}"


def clean_genres(raw: str | list | None) -> list[str]:
    """Convertit une valeur de genres brute (string Python-list ou déjà une liste) en vraie liste."""
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return []
    if isinstance(raw, list):
        return raw
    if isinstance(raw, str):
        raw = raw.strip()
        if not raw:
            return []
        try:
            parsed = ast.literal_eval(
                raw
            )  # ast.literal_eval parse en toute sécurité une string type "['Action', 'Drama']"
            return list(parsed) if isinstance(parsed, list | tuple) else [str(parsed)]
        except (ValueError, SyntaxError):
            return [raw]  # Cas où raw est une simple string non formatée en liste, ex: "Action"
    return []


def prepare_catalogue(df: pd.DataFrame) -> pd.DataFrame:
    """Nettoie le catalogue TMDB brut : ne garde que les films sortis, avec une année exploitable."""
    df = df.copy()

    if "status" in df.columns:
        df = df[df["status"] == "Released"]

    if "release_date" in df.columns:
        release_dates = pd.to_datetime(
            df["release_date"], errors="coerce"
        )  # errors="coerce" transforme toute date invalide/manquante en NaT plutôt que de planter
        df["year"] = release_dates.dt.year

    df = df.dropna(subset=["year"])
    df["year"] = df["year"].astype(int)

    return df.reset_index(drop=True)
