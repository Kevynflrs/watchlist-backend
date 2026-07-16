import io

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app


@pytest.fixture
def client():
    """TestClient FastAPI, avec get_db overridé vers une DB SQLite en mémoire isolée."""
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


def _watched_csv_bytes() -> bytes:
    content = (
        "Date,Name,Year,Letterboxd URI\n"
        "2026-03-04,Scarface,1983,https://boxd.it/2b7g\n"
        "2026-03-15,GoodFellas,1990,https://boxd.it/29FA\n"
    )
    return content.encode("utf-8")


def _ratings_csv_bytes(scarface_rating: float = 5.0) -> bytes:
    content = (
        "Date,Name,Year,Letterboxd URI,Rating\n"
        f"2026-03-04,Scarface,1983,https://boxd.it/2b7g,{scarface_rating}\n"
        "2026-03-15,GoodFellas,1990,https://boxd.it/29FA,3.0\n"
    )
    return content.encode("utf-8")


def test_import_watched_returns_correct_summary(client):
    files = {"file": ("watched.csv", io.BytesIO(_watched_csv_bytes()), "text/csv")}

    response = client.post("/watched/import/watched", files=files)

    assert response.status_code == 200
    body = response.json()
    assert body["file"] == "watched.csv"
    assert body["rows_received"] == 2
    assert body["inserted"] == 2
    assert body["updated"] == 0
    assert body["unchanged"] == 0


def test_uploading_same_csv_twice_gives_zero_new_inserts(client):
    files = {"file": ("ratings.csv", io.BytesIO(_ratings_csv_bytes()), "text/csv")}

    first_response = client.post("/watched/import/ratings", files=files)
    assert first_response.json()["inserted"] == 2

    files_second_pass = {"file": ("ratings.csv", io.BytesIO(_ratings_csv_bytes()), "text/csv")}
    second_response = client.post("/watched/import/ratings", files=files_second_pass)

    body = second_response.json()
    assert body["inserted"] == 0
    assert body["updated"] == 0
    assert body["unchanged"] == 2


def test_modified_rating_increments_updated_count(client):
    files_first = {"file": ("ratings.csv", io.BytesIO(_ratings_csv_bytes(5.0)), "text/csv")}
    client.post("/watched/import/ratings", files=files_first)

    files_modified = {"file": ("ratings.csv", io.BytesIO(_ratings_csv_bytes(4.5)), "text/csv")}
    response = client.post("/watched/import/ratings", files=files_modified)

    body = response.json()
    assert body["updated"] == 1
    assert body["unchanged"] == 1
