import pandas as pd
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.config import TMDB_IMAGE_BASE
from app.database import engine, get_db
from app.models_db import WatchedMovie
from app.routers.train import get_cached_model_bundle
from app.schemas import MovieOut
from app.scoring import score_catalogue

router = APIRouter(prefix="/recommend", tags=["recommend"])


@router.get("/", response_model=list[MovieOut])
def recommend(
    categorie: str | None = None, limit: int = 20, db: Session = Depends(get_db)
) -> list[MovieOut]:
    """Retourne les films les mieux notés prédits par le modèle, non-vus, triés par score."""
    model_bundle = get_cached_model_bundle()
    if model_bundle is None:
        raise HTTPException(
            status_code=409, detail="Aucun modèle entraîné. Appelle POST /train/ d'abord."
        )

    catalogue_df = pd.read_sql("SELECT * FROM movies", con=engine)
    watched_match_keys = {row.match_key for row in db.query(WatchedMovie.match_key).all()}

    scored_df = score_catalogue(catalogue_df, watched_match_keys, model_bundle)

    if categorie is not None:
        scored_df = scored_df[scored_df["categorie_style"] == categorie]

    scored_df = scored_df.sort_values("score_prediction", ascending=False).head(limit)

    return [
        MovieOut(
            title=row["title"],
            year=row["year"],
            genres=[],
            overview=row.get("overview"),
            poster_url=(
                f"{TMDB_IMAGE_BASE}{row['poster_path']}" if row.get("poster_path") else None
            ),
            score_prediction=row["score_prediction"],
        )
        for _, row in scored_df.iterrows()
    ]
