import asyncio
from typing import Any

import httpx

from app.config import TMDB_API_BASE
from app.ml_core import make_match_key
from app.tmdb_client import _get_auth_params_and_headers

MAX_CONCURRENT_REQUESTS = (
    5  # Limite le nombre de requêtes TMDB simultanées, pour éviter le rate limiting.
)


async def _get_with_retry(
    client: httpx.AsyncClient, url: str, params: dict[str, str], headers: dict[str, str]
) -> httpx.Response:
    """Effectue un GET async, en patientant et réessayant automatiquement sur un 429."""
    while True:
        response = await client.get(url, params=params, headers=headers)

        if response.status_code != 429:
            response.raise_for_status()
            return response

        # TMDB indique combien de secondes attendre avant de réessayer.
        retry_after = int(response.headers.get("Retry-After", "1"))
        await asyncio.sleep(retry_after)


async def discover_page(
    client: httpx.AsyncClient, page: int, min_vote_count: int, sort_by: str
) -> list[dict[str, Any]]:
    """Récupère une page de résultats de /discover/movie."""
    params, headers = _get_auth_params_and_headers()
    params["page"] = str(page)
    params["vote_count.gte"] = str(min_vote_count)
    params["sort_by"] = sort_by

    response = await _get_with_retry(client, f"{TMDB_API_BASE}/discover/movie", params, headers)
    return response.json().get("results", [])


async def get_movie_details(client: httpx.AsyncClient, movie_id: int) -> dict[str, Any]:
    """Récupère les détails complets d'un film par son id TMDB."""
    params, headers = _get_auth_params_and_headers()

    response = await _get_with_retry(client, f"{TMDB_API_BASE}/movie/{movie_id}", params, headers)
    return response.json()


async def sync_catalogue(
    max_pages: int = 5,
    min_vote_count: int = 100,
    sort_by: str = "popularity.desc",
    existing_match_keys: set[str] | None = None,
) -> dict[str, Any]:
    """Orchestre le sync complet : discover toutes les pages, puis détails des films nouveaux.

    Si existing_match_keys est fourni, les films dont le match_key (calculé depuis
    title/release_date du discover, avant tout appel de détail) correspond déjà à
    un film connu sont exclus des appels /movie/{id} — économise le quota TMDB.
    """
    existing_match_keys = existing_match_keys or set()
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)

    async def _bounded_discover(client: httpx.AsyncClient, page: int) -> list[dict[str, Any]]:
        async with semaphore:
            return await discover_page(client, page, min_vote_count, sort_by)

    async def _bounded_details(client: httpx.AsyncClient, movie_id: int) -> dict[str, Any]:
        async with semaphore:
            return await get_movie_details(client, movie_id)

    async with httpx.AsyncClient(timeout=30.0) as client:
        # toutes les pages de discover, en parallèle.
        discover_tasks = [_bounded_discover(client, page) for page in range(1, max_pages + 1)]
        pages_results = await asyncio.gather(*discover_tasks)

        # Aplatit les pages en une seule liste, puis déduplique par id (un film peut théoriquement apparaître sur plusieurs pages si le tri change entre deux appels).
        all_movies = [movie for page_results in pages_results for movie in page_results]
        unique_by_id = {movie["id"]: movie for movie in all_movies}

        # Filtre AVANT l'appel de détail : calcule le match_key depuis les champs déjà présents dans la réponse discover (title, release_date),
        # sans requête supplémentaire, et exclut tout film déjà connu en DB.
        new_movies = []
        skipped_existing = 0
        for movie in unique_by_id.values():
            release_date = movie.get("release_date") or ""
            year = int(release_date[:4]) if release_date[:4].isdigit() else None
            match_key = make_match_key(movie.get("title", ""), year)

            if match_key in existing_match_keys:
                skipped_existing += 1
                continue
            new_movies.append(movie)

        # détails de chaque film NOUVEAU uniquement, en parallèle.
        detail_tasks = [_bounded_details(client, movie["id"]) for movie in new_movies]
        detailed_movies = await asyncio.gather(*detail_tasks)

    return {"movies": list(detailed_movies), "skipped_existing": skipped_existing}
