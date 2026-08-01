import pandas as pd


def _parse_csv_genres(raw: str | float | None) -> list[str]:
    """Parse la colonne genres d'un CSV TMDB, au format 'Action, Comedy, Drama'."""
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return []
    return [g.strip() for g in str(raw).split(",") if g.strip()]


def _clean_value(value):
    """Convertit une valeur pandas NaN en None, laisse le reste inchangé."""
    return None if pd.isna(value) else value


def _row_to_pivot(row) -> dict:
    """Convertit une ligne pandas (Series) d'un CSV TMDB vers le format pivot normalisé."""
    release_date = _clean_value(row.get("release_date"))
    release_date = str(release_date) if release_date else None
    year = int(release_date[:4]) if release_date and release_date[:4].isdigit() else None

    return {
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


def parse_tmdb_csv(file) -> list[dict]:
    """Lit un CSV TMDB brut ENTIER et le transforme en liste de dicts au format pivot.

    Adapté aux fichiers de taille raisonnable (endpoint API). Pour un très gros
    fichier (plusieurs Go), utiliser iter_tmdb_csv_chunks à la place, qui ne charge
    jamais tout le fichier en mémoire d'un coup.
    """
    df = pd.read_csv(file)
    return [_row_to_pivot(row) for _, row in df.iterrows()]


def iter_tmdb_csv_chunks(path: str, chunksize: int = 5000):
    """Générateur : lit un gros CSV TMDB par lots de `chunksize` lignes.

    Ne charge jamais l'intégralité du fichier en mémoire, adapté aux exports de plusieurs Go, utilisé par scripts/bulk_import_tmdb_csv.py. 
    Les lignes sans titre exploitable (données corrompues/incomplètes) sont ignorées.
    """
    for chunk_df in pd.read_csv(path, chunksize=chunksize):
        pivoted = [_row_to_pivot(row) for _, row in chunk_df.iterrows()]
        yield [movie for movie in pivoted if movie["title"]]
