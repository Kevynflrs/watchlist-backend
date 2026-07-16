import pandas as pd
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.imports import _upsert_watched
from app.models_db import WatchedMovie


@pytest.fixture
def db_session():
    """Session SQLite en mémoire, fraîche pour chaque test (même pattern que l'issue #7)."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine)
    session = TestSession()
    yield session
    session.close()


def _sample_watched_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Date": ["2026-03-04", "2026-03-15"],
            "Name": ["Scarface", "GoodFellas"],
            "Year": [1983, 1990],
            "Letterboxd URI": ["https://boxd.it/2b7g", "https://boxd.it/29FA"],
        }
    )


def _sample_ratings_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Date": ["2026-03-04", "2026-03-15"],
            "Name": ["Scarface", "GoodFellas"],
            "Year": [1983, 1990],
            "Letterboxd URI": ["https://boxd.it/2b7g", "https://boxd.it/29FA"],
            "Rating": [5.0, 3.0],
        }
    )


def test_first_import_inserts_all_rows(db_session):
    df = _sample_watched_df()

    summary = _upsert_watched(db_session, df, "watched.csv")

    assert summary.inserted == 2
    assert summary.updated == 0
    assert summary.unchanged == 0
    assert db_session.query(WatchedMovie).count() == 2


def test_reimporting_same_csv_only_gives_unchanged(db_session):
    df = _sample_ratings_df()

    _upsert_watched(db_session, df, "ratings.csv")
    summary_second_pass = _upsert_watched(db_session, df, "ratings.csv")

    assert summary_second_pass.inserted == 0
    assert summary_second_pass.updated == 0
    assert summary_second_pass.unchanged == 2


def test_changed_rating_triggers_update(db_session):
    df = _sample_ratings_df()
    _upsert_watched(db_session, df, "ratings.csv")

    df_modified = df.copy()
    df_modified.loc[df_modified["Name"] == "Scarface", "Rating"] = 4.5

    summary = _upsert_watched(db_session, df_modified, "ratings.csv")

    assert summary.updated == 1
    assert summary.unchanged == 1
    updated_movie = db_session.query(WatchedMovie).filter_by(match_key="scarface_1983").first()
    assert updated_movie.rating == 4.5


def test_watched_csv_without_rating_column_sets_rating_none(db_session):
    df = _sample_watched_df()

    _upsert_watched(db_session, df, "watched.csv")

    movie = db_session.query(WatchedMovie).filter_by(match_key="scarface_1983").first()
    assert movie.rating is None
