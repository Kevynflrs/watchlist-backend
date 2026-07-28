import pandas as pd


def _parse_csv_genres(raw: str | float | None) -> list[str]:
    """Parse la colonne genres d'un CSV TMDB, au format 'Action, Comedy, Drama'."""
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return []
    return [g.strip() for g in str(raw).split(",") if g.strip()]


def _clean_value(value):
    """Convertit une valeur pandas NaN en None, laisse le reste inchangé."""
    return None if pd.isna(value) else value


def parse_tmdb_csv(file) -> list[dict]:
    """Lit un CSV TMDB brut et le transforme en liste de dicts au format pivot normalisé."""
    df = pd.read_csv(file)

    movies = []
    for _, row in df.iterrows():
        release_date = _clean_value(row.get("release_date"))
        release_date = str(release_date) if release_date else None
        year = int(release_date[:4]) if release_date and release_date[:4].isdigit() else None

        movies.append(
            {
                "title": _clean_value(row.get("title")),
                "year": year,
                "genres": _parse_csv_genres(row.get("genres")),
                "overview": _clean_value(row.get("overview")),
                "poster_path": _clean_value(row.get("poster_path")),
                "average_rating": _clean_value(row.get("vote_average")),
                "num_votes": _clean_value(row.get("vote_count")),
                "runtime": _clean_value(row.get("runtime")),
                "revenue": _clean_value(row.get("revenue")),
                "budget": _clean_value(row.get("budget")),
                "popularity": _clean_value(row.get("popularity")),
                "status": _clean_value(row.get("status")),
            }
        )
    return movies
