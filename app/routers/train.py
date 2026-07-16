import pandas as pd
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.config import MODEL_PATH
from app.database import engine, get_db
from app.schemas import TrainResult
from app.train import RATING_THRESHOLD, ModelBundle, train_model

router = APIRouter(prefix="/train", tags=["train"])

# Cache en mémoire du dernier ModelBundle chargé, pour éviter de relire le disque à chaque appel de /train/status ou /recommend/.
_model_bundle_cache: ModelBundle | None = None


def get_cached_model_bundle() -> ModelBundle | None:
    """Retourne le ModelBundle en cache, en le chargeant depuis le disque si nécessaire."""
    global _model_bundle_cache

    if _model_bundle_cache is None and MODEL_PATH.exists():
        _model_bundle_cache = ModelBundle.load(MODEL_PATH)

    return _model_bundle_cache


@router.post("/", response_model=TrainResult)
def train(db: Session = Depends(get_db)) -> TrainResult:
    """Entraîne le modèle à partir du catalogue et des films notés en DB, puis le sauvegarde."""
    global _model_bundle_cache

    catalogue_df = pd.read_sql("SELECT * FROM movies", con=engine)
    watched_df = pd.read_sql("SELECT * FROM watched_movies", con=engine)

    model_bundle = train_model(catalogue_df, watched_df)
    model_bundle.save(MODEL_PATH)
    _model_bundle_cache = model_bundle

    rated = watched_df.dropna(subset=["rating"])
    n_positive = int((rated["rating"] >= RATING_THRESHOLD).sum())

    return TrainResult(
        accuracy=model_bundle.metrics["accuracy"],
        n_train=model_bundle.metrics["n_train"],
        n_test=model_bundle.metrics["n_test"],
        n_positive=n_positive,
        n_total_rated=len(rated),
        roc_auc=model_bundle.metrics.get("roc_auc"),
    )


@router.get("/status")
def train_status() -> dict:
    """Indique si un modèle entraîné existe, et retourne ses métriques si oui."""
    model_bundle = get_cached_model_bundle()

    if model_bundle is None:
        return {"model_exists": False}

    return {"model_exists": True, "metrics": model_bundle.metrics}
