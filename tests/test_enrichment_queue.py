from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models_db import EnrichmentQueue, Movie
from app.routers.catalogue import build_enrichment_queue, enrich_catalogue


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine)
    session = TestSession()
    yield session
    session.close()


def _seed_movies(session, n=5, missing=True, start_index=0):
    for i in range(start_index, start_index + n):
        session.add(
            Movie(
                match_key=f"movie {i}_2000",
                title=f"Movie {i}",
                year=2000,
                genres="[]",
                overview=None if missing else "Complet",
                poster_path=None if missing else "/p.jpg",
                status="Released",
            )
        )
    session.commit()


def test_build_queue_adds_only_incomplete_movies(db_session):
    _seed_movies(db_session, n=3, missing=True, start_index=0)
    _seed_movies(db_session, n=2, missing=False, start_index=3)

    result = build_enrichment_queue(db_session)

    assert result["added_to_queue"] == 3
    assert db_session.query(EnrichmentQueue).count() == 3


def test_build_queue_does_not_duplicate_existing_entries(db_session):
    _seed_movies(db_session, n=3, missing=True)
    build_enrichment_queue(db_session)

    result = build_enrichment_queue(db_session)

    assert result["added_to_queue"] == 0
    assert db_session.query(EnrichmentQueue).count() == 3


@patch("app.routers.catalogue.enrich_movie")
def test_enrich_consumes_and_removes_from_queue(mock_enrich, db_session):
    _seed_movies(db_session, n=5, missing=True)
    build_enrichment_queue(db_session)
    mock_enrich.return_value = {"poster_path": "/found.jpg", "overview": "Résumé trouvé."}

    result = enrich_catalogue(limit=2, db=db_session)

    assert result["checked"] == 2
    assert result["enriched"] == 2
    assert result["remaining_in_queue"] == 3
    assert db_session.query(EnrichmentQueue).count() == 3


@patch("app.routers.catalogue.enrich_movie")
def test_enrich_requeues_at_the_back_when_not_found(mock_enrich, db_session):
    _seed_movies(db_session, n=2, missing=True)
    build_enrichment_queue(db_session)
    mock_enrich.return_value = None

    result = enrich_catalogue(limit=10, db=db_session)

    assert result["enriched"] == 0
    # Non trouvés -> renvoyés en fin de file (nouveaux id), pas supprimés définitivement.
    assert result["remaining_in_queue"] == 2
    assert db_session.query(EnrichmentQueue).count() == 2


@patch("app.routers.catalogue.enrich_movie")
def test_enrich_requeues_not_found_movies_at_the_back(mock_enrich, db_session):
    _seed_movies(db_session, n=3, missing=True, start_index=0)
    build_enrichment_queue(db_session)
    mock_enrich.return_value = None  # aucun film trouvé sur TMDB

    result = enrich_catalogue(limit=3, db=db_session)

    assert result["enriched"] == 0
    assert result["remaining_in_queue"] == 3  # toujours 3, mais avec de nouveaux id (fin de file)
    requeued_ids = [row.movie_id for row in db_session.query(EnrichmentQueue).all()]
    assert set(requeued_ids) == {1, 2, 3}
