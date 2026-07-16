import asyncio
from typing import Any

import httpx

from app.config import TMDB_API_BASE
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
    max_pages: int = 5, min_vote_count: int = 100, sort_by: str = "popularity.desc"
) -> list[dict[str, Any]]:
    """Orchestre le sync complet : discover toutes les pages, puis détails de chaque film unique."""
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
        unique_ids = {movie["id"] for movie in all_movies}

        # détails de chaque film unique, en parallèle.
        detail_tasks = [_bounded_details(client, movie_id) for movie_id in unique_ids]
        detailed_movies = await asyncio.gather(*detail_tasks)

    return list(detailed_movies)
