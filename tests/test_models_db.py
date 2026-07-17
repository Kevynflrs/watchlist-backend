import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models_db import Movie, WatchedMovie


@pytest.fixture
def db_session():
    """Fournit une session SQLAlchemy sur une DB SQLite en mémoire, fraîche pour chaque test."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine)
    session = TestSession()
    yield session
    session.close()


def test_create_and_read_movie(db_session):
    """Un Movie créé doit pouvoir être relu tel quel depuis la DB."""
    movie = Movie(match_key="inception_2010", title="Inception", year=2010)
    db_session.add(movie)
    db_session.commit()

    result = db_session.query(Movie).filter_by(match_key="inception_2010").first()

    assert result is not None
    assert result.title == "Inception"
    assert result.year == 2010


def test_match_key_unique_constraint(db_session):
    """Insérer deux Movie avec le même match_key doit lever une erreur."""
    movie1 = Movie(match_key="dune_2021", title="Dune")
    db_session.add(movie1)
    db_session.commit()

    movie2 = Movie(match_key="dune_2021", title="Dune (doublon)")
    db_session.add(movie2)

    with pytest.raises(IntegrityError):
        db_session.commit()


def test_watched_movie_without_rating(db_session):
    """Un WatchedMovie sans rating (nullable) doit s'insérer sans erreur."""
    watched = WatchedMovie(match_key="matrix_1999", title="The Matrix", year=1999, rating=None)
    db_session.add(watched)
    db_session.commit()

    result = db_session.query(WatchedMovie).filter_by(match_key="matrix_1999").first()

    assert result is not None
    assert result.rating is None
