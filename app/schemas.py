from pydantic import BaseModel


class ImportSummary(BaseModel):
    """Résumé retourné après l'import d'un fichier watched.csv ou ratings.csv."""

    file: str
    rows_received: int
    inserted: int
    updated: int
    unchanged: int


class TrainResult(BaseModel):
    """Résultat retourné après un entraînement du modèle."""

    accuracy: float
    n_train: int
    n_test: int
    n_positive: int
    n_total_rated: int
    roc_auc: float | None = None


class MovieOut(BaseModel):
    """Représentation publique d'un film, telle que renvoyée par l'API (catalogue, recommandations)."""

    title: str
    year: int | None = None
    genres: list[str] = []
    overview: str | None = None
    poster_url: str | None = None
    score_prediction: float | None = None
