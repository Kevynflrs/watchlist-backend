from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, func

from app.database import Base


class Movie(Base):
    """Un film du catalogue, construit depuis l'API TMDB."""

    __tablename__ = "movies"

    id = Column(Integer, primary_key=True, index=True)
    match_key = Column(String, unique=True, index=True, nullable=False)
    title = Column(String, nullable=False)
    year = Column(Integer, nullable=True)
    genres = Column(String, nullable=True)  # stocké en JSON-string, ex: '["Action", "Drame"]'
    overview = Column(String, nullable=True)
    poster_path = Column(String, nullable=True)
    average_rating = Column(Float, nullable=True)
    num_votes = Column(Integer, nullable=True)
    runtime = Column(Integer, nullable=True)
    revenue = Column(Float, nullable=True)
    budget = Column(Float, nullable=True)
    popularity = Column(Float, nullable=True)
    status = Column(String, nullable=True)  # ex: "Released", "Post Production"
    updated_at = Column(DateTime(timezone=True), server_default=func.now())


class EnrichmentQueue(Base):
    """File d'attente des films incomplets à enrichir via TMDB, consommée par lots."""

    __tablename__ = "enrichment_queue"

    id = Column(Integer, primary_key=True, index=True)
    movie_id = Column(Integer, ForeignKey("movies.id"), unique=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class WatchedMovie(Base):
    """Un film vu, importé depuis l'historique Letterboxd (watched.csv / ratings.csv)."""

    __tablename__ = "watched_movies"

    id = Column(Integer, primary_key=True, index=True)
    match_key = Column(String, unique=True, index=True, nullable=False)
    title = Column(String, nullable=False)
    year = Column(Integer, nullable=True)
    rating = Column(Float, nullable=True)  # nullable : watched.csv n'a pas toujours de note
    watched_date = Column(DateTime, nullable=True)
    letterboxd_uri = Column(String, nullable=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now())
