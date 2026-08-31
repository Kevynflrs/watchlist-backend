import pandas as pd
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.config import TMDB_IMAGE_BASE
from app.database import get_db
from app.models_db import Movie, WatchedMovie
from app.routers.train import get_cached_model_bundle
from app.scoring import refresh_recommendation_scores
from app.schemas import MovieOut
from app.scoring import score_catalogue

router = APIRouter(prefix="/recommend", tags=["recommend"])


@router.post("/refresh")
def refresh_scores(db: Session = Depends(get_db)) -> dict:
    """Recalcule les scores de tout le catalogue sans réentraîner le modèle."""
    model_bundle = get_cached_model_bundle()
    if model_bundle is None:
        raise HTTPException(status_code=409, detail="Aucun modèle entraîné.")

    count = refresh_recommendation_scores(db, model_bundle)
    return {"scored_movies": count}


@router.get("/", response_model=list[MovieOut])
def recommend(
    categorie: str | None = None, limit: int = 20, db: Session = Depends(get_db)
) -> list[MovieOut]:
    """Retourne les films les mieux notés (scores déjà pré-calculés), non-vus, triés."""
    model_bundle = get_cached_model_bundle()
    if model_bundle is None:
        raise HTTPException(
            status_code=409, detail="Aucun modèle entraîné. Appelle POST /train/ d'abord."
        )

    watched_subquery = db.query(WatchedMovie.match_key).subquery()

    query = db.query(Movie).filter(
        Movie.score_prediction.isnot(None),
        Movie.match_key.notin_(db.query(watched_subquery.c.match_key)),
    )
    if categorie is not None:
        query = query.filter(Movie.categorie_style == categorie)

    movies = query.order_by(Movie.score_prediction.desc()).limit(limit).all()

    return [
        MovieOut(
            title=movie.title,
            year=movie.year,
            genres=[],
            overview=movie.overview,
            poster_url=f"{TMDB_IMAGE_BASE}{movie.poster_path}" if movie.poster_path else None,
            score_prediction=movie.score_prediction,
        )
        for movie in movies
    ]
