import pandas as pd
from sqlalchemy.orm import Session

from app.ml_core import make_match_key
from app.models_db import WatchedMovie
from app.schemas import ImportSummary


def _upsert_watched(db: Session, df: pd.DataFrame, filename: str) -> ImportSummary:
    """Insère ou met à jour chaque ligne du CSV Letterboxd, sans jamais dupliquer un film."""
    inserted = 0
    updated = 0
    unchanged = 0

    for _, row in df.iterrows():
        match_key = make_match_key(row["Name"], row["Year"])

        rating = row["Rating"] if "Rating" in df.columns and pd.notna(row.get("Rating")) else None
        watched_date = pd.to_datetime(row["Date"], errors="coerce")

        existing = db.query(WatchedMovie).filter_by(match_key=match_key).first()

        if existing is None:
            new_movie = WatchedMovie(
                match_key=match_key,
                title=row["Name"],
                year=int(row["Year"]) if pd.notna(row["Year"]) else None,
                rating=rating,
                watched_date=watched_date if pd.notna(watched_date) else None,
                letterboxd_uri=row.get("Letterboxd URI"),
            )
            db.add(new_movie)
            inserted += 1
            continue

        # On ne met à jour que si rating ou watched_date ont changé.
        has_changed = existing.rating != rating or existing.watched_date != (
            watched_date if pd.notna(watched_date) else None
        )

        if has_changed:
            existing.rating = rating
            existing.watched_date = watched_date if pd.notna(watched_date) else None
            updated += 1
        else:
            unchanged += 1

    db.commit()

    return ImportSummary(
        file=filename,
        rows_received=len(df),
        inserted=inserted,
        updated=updated,
        unchanged=unchanged,
    )
