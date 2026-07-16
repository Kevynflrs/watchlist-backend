import pandas as pd
from fastapi import APIRouter, Depends, UploadFile
from sqlalchemy.orm import Session

from app.database import get_db
from app.imports import _upsert_watched
from app.models_db import WatchedMovie
from app.schemas import ImportSummary

router = APIRouter(prefix="/watched", tags=["watched"])


@router.post("/import/watched", response_model=ImportSummary)
async def import_watched(file: UploadFile, db: Session = Depends(get_db)) -> ImportSummary:
    """Importe un fichier watched.csv exporté depuis Letterboxd."""
    df = pd.read_csv(file.file)
    return _upsert_watched(db, df, file.filename)


@router.post("/import/ratings", response_model=ImportSummary)
async def import_ratings(file: UploadFile, db: Session = Depends(get_db)) -> ImportSummary:
    """Importe un fichier ratings.csv exporté depuis Letterboxd."""
    df = pd.read_csv(file.file)
    return _upsert_watched(db, df, file.filename)


@router.get("/", response_model=list[dict])
def list_watched(db: Session = Depends(get_db)) -> list[dict]:
    """Liste simple des films vus en DB, pour debug rapide."""
    movies = db.query(WatchedMovie).all()
    return [
        {
            "match_key": m.match_key,
            "title": m.title,
            "year": m.year,
            "rating": m.rating,
        }
        for m in movies
    ]
