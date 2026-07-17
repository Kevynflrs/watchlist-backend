from unittest.mock import AsyncMock, patch

import httpx
import pytest

from app.tmdb_async_client import _get_with_retry, sync_catalogue


@pytest.mark.asyncio
async def test_get_with_retry_returns_response_on_success():
    mock_client = AsyncMock()
    fake_response = httpx.Response(
        200, json={"results": []}, request=httpx.Request("GET", "http://test")
    )
    mock_client.get.return_value = fake_response

    result = await _get_with_retry(mock_client, "http://test", {}, {})

    assert result.status_code == 200
    mock_client.get.assert_called_once()


@pytest.mark.asyncio
async def test_get_with_retry_retries_after_429(monkeypatch):
    mock_client = AsyncMock()
    request = httpx.Request("GET", "http://test")
    rate_limited = httpx.Response(429, headers={"Retry-After": "0"}, request=request)
    success = httpx.Response(200, json={"results": []}, request=request)
    mock_client.get.side_effect = [rate_limited, success]

    sleep_calls = []

    async def fake_sleep(seconds):
        sleep_calls.append(seconds)

    monkeypatch.setattr("asyncio.sleep", fake_sleep)

    result = await _get_with_retry(mock_client, "http://test", {}, {})

    assert result.status_code == 200
    assert mock_client.get.call_count == 2
    assert sleep_calls == [0]


@pytest.mark.asyncio
async def test_sync_catalogue_deduplicates_movies_across_pages():
    request = httpx.Request("GET", "http://test")

    async def fake_get(url, params=None, headers=None):
        if "discover" in url:
            # Deux pages avec un film en commun (id=1) pour vérifier la dédup.
            page = int(params["page"])
            if page == 1:
                results = [{"id": 1, "title": "Movie A"}, {"id": 2, "title": "Movie B"}]
            else:
                results = [{"id": 1, "title": "Movie A"}, {"id": 3, "title": "Movie C"}]
            return httpx.Response(200, json={"results": results}, request=request)
        # /movie/{id}
        movie_id = int(url.rsplit("/", 1)[-1])
        return httpx.Response(
            200, json={"id": movie_id, "title": f"Movie {movie_id}"}, request=request
        )

    with patch("httpx.AsyncClient.get", new=AsyncMock(side_effect=fake_get)):
        result = await sync_catalogue(max_pages=2, min_vote_count=100)

    result_ids = {movie["id"] for movie in result}
    assert result_ids == {1, 2, 3}
    assert len(result) == 3
