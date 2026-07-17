import io

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.routers.train as train_module
from app.database import Base, get_db
from app.main import app
from app.models_db import Movie


@pytest.fixture(autouse=True)
def isolate_model_path(tmp_path, monkeypatch):
    """Empêche les tests de lire/écrire le vrai models/model_bundle.joblib de la machine."""
    monkeypatch.setattr(train_module, "MODEL_PATH", tmp_path / "test_model_bundle.joblib")
    monkeypatch.setattr(train_module, "_model_bundle_cache", None)


@pytest.fixture
def client_and_session():
    """TestClient FastAPI + accès direct à la session de test, pour insérer des Movie factices."""
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
    yield TestClient(app), TestSession()
    app.dependency_overrides.clear()


def _seed_catalogue(session, n: int = 30) -> None:
    """Insère n films factices directement en DB, avec des genres/notes variés."""
    genres_cycle = ['["Action"]', '["Comedy"]', '["Drama"]', '["Action", "Drama"]']
    for i in range(n):
        session.add(
            Movie(
                match_key=f"movie {i}_{2000 + i % 24}",
                title=f"Movie {i}",
                year=2000 + i % 24,
                genres=genres_cycle[i % len(genres_cycle)],
                overview="Un film de test.",
                poster_path="/poster.jpg",
                average_rating=5.0 + (i % 5),
                num_votes=100 + i * 50,
                runtime=90 + i,
                revenue=1_000_000.0 * i,
                popularity=float(i),
                status="Released",
            )
        )
    session.commit()


def _ratings_csv_bytes(n: int = 25) -> bytes:
    """Génère un CSV de notes couvrant les n premiers films factices insérés par _seed_catalogue."""
    lines = ["Date,Name,Year,Letterboxd URI,Rating"]
    for i in range(n):
        rating = [1.0, 2.0, 3.0, 3.5, 4.0, 4.5, 5.0][i % 7]
        lines.append(f"2026-01-01,Movie {i},{2000 + i % 24},https://boxd.it/x{i},{rating}")
    return "\n".join(lines).encode("utf-8")


def test_recommend_without_trained_model_returns_409(client_and_session):
    client, _ = client_and_session

    response = client.get("/recommend/")

    assert response.status_code == 409


def test_full_scenario_import_train_recommend(client_and_session):
    client, session = client_and_session

    # Étape 1 : peuple le catalogue.
    _seed_catalogue(session, n=30)

    # Étape 2 : importe les notes Letterboxd, via le vrai endpoint HTTP.
    files = {"file": ("ratings.csv", io.BytesIO(_ratings_csv_bytes(n=25)), "text/csv")}
    import_response = client.post("/watched/import/ratings", files=files)
    assert import_response.status_code == 200
    assert import_response.json()["inserted"] == 25

    # Étape 3 : entraîne le modèle via l'endpoint réel.
    train_response = client.post("/train/")
    assert train_response.status_code == 200
    train_body = train_response.json()
    assert train_body["n_train"] + train_body["n_test"] == 25

    # Étape 4 : récupère les recommandations via l'endpoint réel.
    recommend_response = client.get("/recommend/", params={"limit": 10})
    assert recommend_response.status_code == 200
    recommendations = recommend_response.json()

    # Les 25 films notés ne doivent jamais apparaître dans les recommandations.
    recommended_titles = {movie["title"] for movie in recommendations}
    watched_titles = {f"Movie {i}" for i in range(25)}
    assert recommended_titles.isdisjoint(watched_titles)

    # Les 5 films restants sont les seuls candidats possibles.
    assert recommended_titles.issubset({f"Movie {i}" for i in range(25, 30)})
    assert len(recommendations) <= 5
