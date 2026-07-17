from typing import Any

import httpx

from app.config import TMDB_API_BASE, TMDB_API_KEY, TMDB_BEARER_TOKEN


def _get_auth_params_and_headers() -> tuple[dict[str, str], dict[str, str]]:
    """Construit params/headers d'authentification : Bearer en priorité, sinon api_key en fallback."""
    if TMDB_BEARER_TOKEN:
        return {}, {"Authorization": f"Bearer {TMDB_BEARER_TOKEN}"}
    return {"api_key": TMDB_API_KEY}, {}


def search_movie(title: str, year: int | None = None) -> dict[str, Any] | None:
    """Cherche un film sur TMDB par titre (et année si fournie), retourne le premier résultat."""
    params, headers = _get_auth_params_and_headers()
    params["query"] = title
    if year is not None:
        params["year"] = str(year)

    response = httpx.get(f"{TMDB_API_BASE}/search/movie", params=params, headers=headers)
    response.raise_for_status()
    results = response.json().get("results", [])

    return results[0] if results else None


def enrich_movie(title: str, year: int | None = None) -> dict[str, Any] | None:
    """Cherche puis reformate un film TMDB pour correspondre au schéma du modèle Movie."""
    found = search_movie(title, year)
    if found is None:
        return None

    return {
        "title": found.get("title"),
        "overview": found.get("overview"),
        "poster_path": found.get("poster_path"),
        "average_rating": found.get("vote_average"),
        "num_votes": found.get("vote_count"),
        "popularity": found.get("popularity"),
        "status": "Released",
        "release_date": found.get("release_date"),
    }
