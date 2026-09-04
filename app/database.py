from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker

from app.config import DATABASE_URL

# SQLite refuse par défaut le partage d'une connexion entre threads.
# On désactive cette vérification uniquement pour SQLite, car uvicorn peut traiter les requêtes dans des threads différents.
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args)

# Chaque appel à SessionLocal() crée une nouvelle session indépendante, liée à `engine`.
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Classe de base dont hériteront tous les modèles ORM (Movie, WatchedMovie...).
Base = declarative_base()


def ensure_recommendation_columns(engine) -> None:
    """Ajoute score_prediction/categorie_style à movies si absentes (pas d'Alembic ici)."""
    from sqlalchemy import inspect, text

    inspector = inspect(engine)
    existing_columns = {col["name"] for col in inspector.get_columns("movies")}

    with engine.begin() as conn:
        if "score_prediction" not in existing_columns:
            conn.execute(text("ALTER TABLE movies ADD COLUMN score_prediction FLOAT"))
        if "categorie_style" not in existing_columns:
            conn.execute(text("ALTER TABLE movies ADD COLUMN categorie_style VARCHAR"))


def get_db() -> Generator[Session, None, None]:
    """Fournit une session DB à une route FastAPI, et la ferme systématiquement après usage."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
