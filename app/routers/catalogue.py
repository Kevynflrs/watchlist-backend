from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.ml_core import make_match_key
from app.models_db import Movie
from app.tmdb_async_client import sync_catalogue
from app.tmdb_client import enrich_movie

router = APIRouter(prefix="/catalogue", tags=["catalogue"])


def _upsert_movies(db: Session, raw_movies: list[dict]) -> dict[str, int]:
    """Insère ou met à jour chaque film TMDB brut en DB, par match_key."""
    inserted = 0
    updated = 0
    unchanged = 0

    for raw in raw_movies:
        title = raw.get("title", "")
        release_date = raw.get("release_date") or ""
        year = int(release_date[:4]) if release_date[:4].isdigit() else None
        match_key = make_match_key(title, year)

        genres = [g["name"] for g in raw.get("genres", [])] if raw.get("genres") else []

        new_values = {
            "title": title,
            "year": year,
            "genres": str(genres),
            "overview": raw.get("overview"),
            "poster_path": raw.get("poster_path"),
            "average_rating": raw.get("vote_average"),
            "num_votes": raw.get("vote_count"),
            "runtime": raw.get("runtime"),
            "revenue": raw.get("revenue"),
            "budget": raw.get("budget"),
            "popularity": raw.get("popularity"),
            "status": raw.get("status"),
        }

        existing = db.query(Movie).filter_by(match_key=match_key).first()

        if existing is None:
            db.add(Movie(match_key=match_key, **new_values))
            inserted += 1
            continue

        has_changed = any(getattr(existing, field) != value for field, value in new_values.items())

        if has_changed:
            for field, value in new_values.items():
                setattr(existing, field, value)
            updated += 1
        else:
            unchanged += 1

    db.commit()

    return {"inserted": inserted, "updated": updated, "unchanged": unchanged}


@router.post("/sync")
async def sync_catalogue_endpoint(
    max_pages: int = 5,
    min_vote_count: int = 100,
    sort_by: str = "popularity.desc",
    db: Session = Depends(get_db),
) -> dict:
    """Synchronise le catalogue local depuis TMDB (discover paginé + détails par film)."""
    raw_movies = await sync_catalogue(
        max_pages=max_pages, min_vote_count=min_vote_count, sort_by=sort_by
    )
    summary = _upsert_movies(db, raw_movies)

    return {"movies_fetched": len(raw_movies), **summary}


@router.post("/enrich")
def enrich_catalogue(limit: int = 20, db: Session = Depends(get_db)) -> dict:
    """Complète les films du catalogue dont le poster ou le résumé manque, via TMDB."""
    incomplete_movies = (
        db.query(Movie)
        .filter((Movie.poster_path.is_(None)) | (Movie.overview == ""))
        .limit(limit)
        .all()
    )

    checked = 0
    enriched = 0
    errors = 0

    for movie in incomplete_movies:
        checked += 1
        try:
            found = enrich_movie(movie.title, movie.year)
        except Exception:
            errors += 1
            continue

        if found is None:
            continue

        if found.get("poster_path"):
            movie.poster_path = found["poster_path"]
        if found.get("overview"):
            movie.overview = found["overview"]

        enriched += 1

    db.commit()

    return {"checked": checked, "enriched": enriched, "errors": errors}
