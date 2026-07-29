import pytest

from app.tmdb_async_client import sync_catalogue


@pytest.mark.asyncio
async def test_sync_catalogue_skips_known_movies(monkeypatch):
    """Un film déjà dans existing_match_keys ne doit jamais déclencher d'appel de détail."""
    discover_results = {
        1: [
            {"id": 1, "title": "Movie A", "release_date": "2010-01-01"},
            {"id": 2, "title": "Movie B", "release_date": "2015-06-15"},
        ]
    }

    detail_calls = []

    async def fake_discover_page(client, page, min_vote_count, sort_by):
        return discover_results.get(page, [])

    async def fake_get_movie_details(client, movie_id):
        detail_calls.append(movie_id)
        return {"id": movie_id, "title": f"Movie {movie_id}"}

    monkeypatch.setattr("app.tmdb_async_client.discover_page", fake_discover_page)
    monkeypatch.setattr("app.tmdb_async_client.get_movie_details", fake_get_movie_details)

    # "Movie A" (2010) est déjà connu -> son match_key doit matcher et l'exclure.
    existing_match_keys = {"movie a_2010"}

    result = await sync_catalogue(max_pages=1, existing_match_keys=existing_match_keys)

    assert detail_calls == [2]
    assert result["skipped_existing"] == 1
    assert len(result["movies"]) == 1
    assert result["movies"][0]["id"] == 2


@pytest.mark.asyncio
async def test_sync_catalogue_without_existing_keys_fetches_everything(monkeypatch):
    """Sans existing_match_keys (comportement historique), tous les films sont détaillés."""

    async def fake_discover_page(client, page, min_vote_count, sort_by):
        return [{"id": 1, "title": "Movie A", "release_date": "2010-01-01"}]

    async def fake_get_movie_details(client, movie_id):
        return {"id": movie_id, "title": "Movie A"}

    monkeypatch.setattr("app.tmdb_async_client.discover_page", fake_discover_page)
    monkeypatch.setattr("app.tmdb_async_client.get_movie_details", fake_get_movie_details)

    result = await sync_catalogue(max_pages=1)

    assert result["skipped_existing"] == 0
    assert len(result["movies"]) == 1
