from unittest.mock import MagicMock, patch

from app.tmdb_client import enrich_movie, search_movie


def _fake_tmdb_response(results: list[dict]) -> MagicMock:
    mock_response = MagicMock()
    mock_response.json.return_value = {"results": results}
    mock_response.raise_for_status.return_value = None
    return mock_response


@patch("app.tmdb_client.httpx.get")
def test_search_movie_returns_first_result(mock_get):
    mock_get.return_value = _fake_tmdb_response(
        [{"title": "Inception", "id": 27205}, {"title": "Inception 2", "id": 99999}]
    )

    result = search_movie("Inception", 2010)

    assert result["title"] == "Inception"
    assert result["id"] == 27205


@patch("app.tmdb_client.httpx.get")
def test_search_movie_returns_none_when_no_results(mock_get):
    mock_get.return_value = _fake_tmdb_response([])

    result = search_movie("Un Film Qui N'Existe Absolument Pas")

    assert result is None


@patch("app.tmdb_client.httpx.get")
def test_enrich_movie_reformats_fields_correctly(mock_get):
    mock_get.return_value = _fake_tmdb_response(
        [
            {
                "title": "Inception",
                "overview": "A thief who steals corporate secrets...",
                "poster_path": "/poster.jpg",
                "vote_average": 8.4,
                "vote_count": 35000,
                "popularity": 95.2,
                "release_date": "2010-07-16",
            }
        ]
    )

    result = enrich_movie("Inception", 2010)

    assert result["title"] == "Inception"
    assert result["average_rating"] == 8.4
    assert result["num_votes"] == 35000
    assert result["status"] == "Released"
    assert result["release_date"] == "2010-07-16"


@patch("app.tmdb_client.httpx.get")
def test_enrich_movie_returns_none_when_not_found(mock_get):
    mock_get.return_value = _fake_tmdb_response([])

    result = enrich_movie("Film Inconnu")

    assert result is None
