import httpx
import pytest
import respx
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import TMDB_API_BASE
from app.database import Base, get_db
from app.main import app
from app.tmdb_async_client import sync_catalogue


@pytest.fixture
def client():
    """TestClient FastAPI avec DB SQLite en mémoire isolée (même pattern que l'issue #16)."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine)

    def override_get_db():
        db = TestSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.mark.asyncio
@respx.mock
async def test_sync_catalogue_returns_deduplicated_movies():
    """sync_catalogue() : 2 pages avec un film en commun -> résultat dédupliqué."""
    respx.get(f"{TMDB_API_BASE}/discover/movie", params={"page": "1"}).mock(
        return_value=httpx.Response(
            200, json={"results": [{"id": 1, "title": "Movie A"}, {"id": 2, "title": "Movie B"}]}
        )
    )
    respx.get(f"{TMDB_API_BASE}/discover/movie", params={"page": "2"}).mock(
        return_value=httpx.Response(
            200, json={"results": [{"id": 1, "title": "Movie A"}, {"id": 3, "title": "Movie C"}]}
        )
    )
    respx.get(url__regex=rf"{TMDB_API_BASE}/movie/\d+").mock(
        side_effect=lambda request: httpx.Response(
            200, json={"id": int(request.url.path.rsplit("/", 1)[-1]), "title": "Detail"}
        )
    )

    result = await sync_catalogue(max_pages=2, min_vote_count=100)

    result_ids = {movie["id"] for movie in result}
    assert result_ids == {1, 2, 3}


@pytest.mark.asyncio
@respx.mock
async def test_sync_catalogue_retries_on_429():
    """Une réponse 429 suivie d'un 200 doit être gérée automatiquement, sans erreur remontée."""
    route = respx.get(f"{TMDB_API_BASE}/discover/movie").mock(
        side_effect=[
            httpx.Response(429, headers={"Retry-After": "0"}),
            httpx.Response(200, json={"results": [{"id": 1, "title": "Movie A"}]}),
        ]
    )
    respx.get(url__regex=rf"{TMDB_API_BASE}/movie/\d+").mock(
        return_value=httpx.Response(200, json={"id": 1, "title": "Detail"})
    )

    result = await sync_catalogue(max_pages=1, min_vote_count=100)

    assert route.call_count == 2
    assert len(result) == 1


@respx.mock
def test_sync_endpoint_full_flow_via_testclient(client):
    """L'endpoint POST /catalogue/sync complet, TestClient + respx, aucun vrai appel réseau."""
    respx.get(f"{TMDB_API_BASE}/discover/movie").mock(
        return_value=httpx.Response(
            200,
            json={
                "results": [
                    {"id": 42, "title": "Test Movie", "release_date": "2020-01-01"},
                ]
            },
        )
    )
    respx.get(url__regex=rf"{TMDB_API_BASE}/movie/\d+").mock(
        return_value=httpx.Response(
            200,
            json={
                "id": 42,
                "title": "Test Movie",
                "release_date": "2020-01-01",
                "overview": "A test movie.",
                "vote_average": 7.5,
                "vote_count": 1000,
                "popularity": 42.0,
                "status": "Released",
                "genres": [{"id": 1, "name": "Drama"}],
            },
        )
    )

    response = client.post("/catalogue/sync", params={"max_pages": 1, "min_vote_count": 100})

    assert response.status_code == 200
    body = response.json()
    assert body["movies_fetched"] == 1
    assert body["inserted"] == 1
