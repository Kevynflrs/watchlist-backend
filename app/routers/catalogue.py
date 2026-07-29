from fastapi import APIRouter, Depends, UploadFile
from sqlalchemy.orm import Session

from app.database import get_db
from app.ml_core import make_match_key
from app.models_db import EnrichmentQueue, Movie
from app.tmdb_async_client import sync_catalogue
from app.tmdb_client import enrich_movie
from app.tmdb_csv_import import parse_tmdb_csv

router = APIRouter(prefix="/catalogue", tags=["catalogue"])


def _normalize_tmdb_api_movie(raw: dict) -> dict:
    """Convertit un film brut de l'API TMDB (/movie/{id}) vers le format pivot normalisé."""
    release_date = raw.get("release_date") or ""
    year = int(release_date[:4]) if release_date[:4].isdigit() else None
    genres = [g["name"] for g in raw.get("genres", [])] if raw.get("genres") else []

    return {
        "title": raw.get("title", ""),
        "year": year,
        "genres": genres,
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


def _is_empty(value) -> bool:
    """Considère None, chaîne vide, et 'liste vide sérialisée' comme des valeurs manquantes."""
    return value is None or value == "" or value == "[]"


def _upsert_movies(
    db: Session, movies: list[dict], fill_missing_only: bool = False
) -> dict[str, int]:
    """Insère ou met à jour chaque film normalisé en DB, par match_key.

    Si fill_missing_only=True, ne modifie que les champs actuellement vides en DB
    (ne remplace jamais une valeur déjà présente) — utile pour un import CSV qui
    ne doit pas dégrader des données déjà à jour via /catalogue/sync.
    """
    inserted = 0
    updated = 0
    unchanged = 0
    skipped_duplicates = 0

    # Suit les match_key déjà traités dans CE batch, pour détecter les doublons internes au fichier importé avant qu'ils ne soient tentés en DB sans avoir été flush.
    seen_in_batch: set[str] = set()

    for movie in movies:
        match_key = make_match_key(movie["title"], movie["year"])

        if match_key in seen_in_batch:
            skipped_duplicates += 1
            continue
        seen_in_batch.add(match_key)

        new_values = {**movie, "genres": str(movie["genres"])}

        existing = db.query(Movie).filter_by(match_key=match_key).first()

        if existing is None:
            db.add(Movie(match_key=match_key, **new_values))
            inserted += 1
            continue

        if fill_missing_only:
            # Ne retient que les champs où l'existant est vide ET la nouvelle valeur ne l'est pas.
            fields_to_fill = {
                field: value
                for field, value in new_values.items()
                if _is_empty(getattr(existing, field)) and not _is_empty(value)
            }
            if fields_to_fill:
                for field, value in fields_to_fill.items():
                    setattr(existing, field, value)
                updated += 1
            else:
                unchanged += 1
            continue

        has_changed = any(getattr(existing, field) != value for field, value in new_values.items())

        if has_changed:
            for field, value in new_values.items():
                setattr(existing, field, value)
            updated += 1
        else:
            unchanged += 1

    db.commit()

    return {
        "inserted": inserted,
        "updated": updated,
        "unchanged": unchanged,
        "skipped_duplicates": skipped_duplicates,
    }


@router.post("/sync")
async def sync_catalogue_endpoint(
    max_pages: int = 5,
    min_vote_count: int = 100,
    sort_by: str = "popularity.desc",
    db: Session = Depends(get_db),
) -> dict:
    """Synchronise le catalogue local depuis TMDB (discover paginé + détails des films nouveaux)."""
    existing_match_keys = {row.match_key for row in db.query(Movie.match_key).all()}

    result = await sync_catalogue(
        max_pages=max_pages,
        min_vote_count=min_vote_count,
        sort_by=sort_by,
        existing_match_keys=existing_match_keys,
    )
    raw_movies = result["movies"]

    normalized_movies = [_normalize_tmdb_api_movie(raw) for raw in raw_movies]
    summary = _upsert_movies(db, normalized_movies)

    return {
        "movies_fetched": len(raw_movies),
        "skipped_existing": result["skipped_existing"],
        **summary,
    }


@router.get("/stats")
def catalogue_stats(db: Session = Depends(get_db)) -> dict:
    """Retourne des statistiques simples sur le catalogue actuellement en DB."""
    total = db.query(Movie).count()
    missing_poster = db.query(Movie).filter(Movie.poster_path.is_(None)).count()
    missing_overview = (
        db.query(Movie).filter((Movie.overview.is_(None)) | (Movie.overview == "")).count()
    )

    return {
        "total_movies": total,
        "missing_poster": missing_poster,
        "missing_overview": missing_overview,
    }


@router.post("/import")
def import_catalogue_csv(
    file: UploadFile, fill_missing_only: bool = True, db: Session = Depends(get_db)
) -> dict:
    """Importe/actualise le catalogue depuis un export CSV TMDB local.

    Par défaut (fill_missing_only=True), ne comble que les champs vides en DB,
    sans jamais écraser une donnée déjà présente (ex: via /catalogue/sync).
    Passe fill_missing_only=false pour un comportement d'écrasement complet.
    """
    movies = parse_tmdb_csv(file.file)
    summary = _upsert_movies(db, movies, fill_missing_only=fill_missing_only)

    return {"movies_read": len(movies), **summary}


@router.post("/enrich/queue/build")
def build_enrichment_queue(db: Session = Depends(get_db)) -> dict:
    """Ajoute à la file d'attente tous les films incomplets pas encore présents dedans."""
    already_queued_ids = {row.movie_id for row in db.query(EnrichmentQueue.movie_id).all()}

    incomplete_movies = (
        db.query(Movie)
        .filter((Movie.poster_path.is_(None)) | (Movie.overview.is_(None)) | (Movie.overview == ""))
        .all()
    )

    added = 0
    for movie in incomplete_movies:
        if movie.id in already_queued_ids:
            continue
        db.add(EnrichmentQueue(movie_id=movie.id))
        added += 1

    db.commit()

    return {"added_to_queue": added, "queue_size": db.query(EnrichmentQueue).count()}


@router.get("/enrich/queue")
def enrichment_queue_status(db: Session = Depends(get_db)) -> dict:
    """Retourne le nombre de films actuellement en attente d'enrichissement."""
    return {"queue_size": db.query(EnrichmentQueue).count()}


@router.post("/enrich")
def enrich_catalogue(limit: int = 20, db: Session = Depends(get_db)) -> dict:
    """Complète les `limit` prochains films de la file d'attente, via TMDB, puis les en retire."""
    queue_entries = db.query(EnrichmentQueue).order_by(EnrichmentQueue.id).limit(limit).all()

    checked = 0
    enriched = 0
    errors = 0

    for entry in queue_entries:
        checked += 1
        movie = db.query(Movie).filter_by(id=entry.movie_id).first()

        if movie is None:
            # Le film a été supprimé du catalogue depuis sa mise en file -> on nettoie juste la file.
            db.delete(entry)
            continue

        try:
            found = enrich_movie(movie.title, movie.year)
        except Exception:
            errors += 1
            # Échec technique : renvoyé en fin de file (nouvel id) plutôt que perdu, pour ne pas bloquer les films suivants tout en gardant une chance de retry.
            db.delete(entry)
            db.flush()
            db.add(EnrichmentQueue(movie_id=entry.movie_id))
            continue

        if found is None:
            # TMDB n'a rien trouvé cette fois -> même logique, renvoyé en fin de file.
            db.delete(entry)
            db.flush()
            db.add(EnrichmentQueue(movie_id=entry.movie_id))
            continue

        if found.get("poster_path"):
            movie.poster_path = found["poster_path"]
        if found.get("overview"):
            movie.overview = found["overview"]
        enriched += 1

        # Enrichissement réussi : plus besoin de garder ce film en file.
        db.delete(entry)

    db.commit()

    return {
        "checked": checked,
        "enriched": enriched,
        "errors": errors,
        "remaining_in_queue": db.query(EnrichmentQueue).count(),
    }
