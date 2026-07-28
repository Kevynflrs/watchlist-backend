"""Tests du parsing CSV TMDB et de l'upsert normalisé partagé."""

import io

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models_db import Movie
from app.routers.catalogue import _normalize_tmdb_api_movie, _upsert_movies
from app.tmdb_csv_import import parse_tmdb_csv


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine)
    session = TestSession()
    yield session
    session.close()


def _sample_csv_bytes() -> bytes:
    content = (
        "id,title,vote_average,vote_count,status,release_date,revenue,runtime,"
        "budget,overview,popularity,poster_path,genres\n"
        "27205,Inception,8.4,35000,Released,2010-07-16,825000000,148,"
        '160000000,A thief who steals secrets,95.2,/poster.jpg,"Action, Sci-Fi"\n'
    )
    return content.encode("utf-8")


def test_parse_tmdb_csv_produces_pivot_format():
    movies = parse_tmdb_csv(io.BytesIO(_sample_csv_bytes()))

    assert len(movies) == 1
    movie = movies[0]
    assert movie["title"] == "Inception"
    assert movie["year"] == 2010
    assert movie["genres"] == ["Action", "Sci-Fi"]
    assert movie["average_rating"] == 8.4


def test_normalize_tmdb_api_movie_matches_pivot_format():
    raw_api_movie = {
        "title": "Inception",
        "release_date": "2010-07-16",
        "genres": [{"id": 28, "name": "Action"}, {"id": 878, "name": "Sci-Fi"}],
        "vote_average": 8.4,
    }

    normalized = _normalize_tmdb_api_movie(raw_api_movie)

    assert normalized["year"] == 2010
    assert normalized["genres"] == ["Action", "Sci-Fi"]
    assert normalized["average_rating"] == 8.4


def test_upsert_movies_inserts_from_csv_pivot_format(db_session):
    movies = parse_tmdb_csv(io.BytesIO(_sample_csv_bytes()))

    summary = _upsert_movies(db_session, movies)

    assert summary == {
        "inserted": 1,
        "updated": 0,
        "unchanged": 0,
        "skipped_duplicates": 0,
    }
    stored = db_session.query(Movie).filter_by(match_key="inception_2010").first()
    assert stored.title == "Inception"
    assert stored.genres == "['Action', 'Sci-Fi']"


def test_upsert_movies_shared_between_csv_and_api_sources(db_session):
    csv_movies = parse_tmdb_csv(io.BytesIO(_sample_csv_bytes()))
    _upsert_movies(db_session, csv_movies)

    # Le même film revient via l'API TMDB (format brut différent) -> doit matcher le même match_key.
    api_movie = _normalize_tmdb_api_movie(
        {
            "title": "Inception",
            "release_date": "2010-07-16",
            "genres": [{"id": 28, "name": "Action"}, {"id": 878, "name": "Sci-Fi"}],
            "vote_average": 8.4,
            "vote_count": 35000,
            "runtime": 148,
            "budget": 160000000,
            "revenue": 825000000,
            "overview": "A thief who steals secrets",
            "popularity": 95.2,
            "poster_path": "/poster.jpg",
            "status": "Released",
        }
    )
    summary = _upsert_movies(db_session, [api_movie])

    assert summary["unchanged"] == 1
    assert db_session.query(Movie).count() == 1


def test_upsert_movies_skips_duplicate_match_key_within_same_batch(db_session):
    movies = [
        {
            "title": "War of the Buttons",
            "year": 2011,
            "genres": ["Family"],
            "overview": "Version française",
            "poster_path": None,
            "average_rating": 6.0,
            "num_votes": 300,
            "runtime": 100,
            "revenue": 0,
            "budget": 0,
            "popularity": 5.0,
            "status": "Released",
        },
        {
            "title": "War of the Buttons",
            "year": 2011,
            "genres": ["Comedy"],
            "overview": "Version anglaise",
            "poster_path": None,
            "average_rating": 5.0,
            "num_votes": 100,
            "runtime": 90,
            "revenue": 0,
            "budget": 0,
            "popularity": 2.0,
            "status": "Released",
        },
    ]

    summary = _upsert_movies(db_session, movies)

    assert summary["inserted"] == 1
    assert summary["skipped_duplicates"] == 1
    assert db_session.query(Movie).count() == 1
