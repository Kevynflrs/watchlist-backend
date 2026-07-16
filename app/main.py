from fastapi import FastAPI

from app.database import Base, engine
from app.routers import watched

# Crée toutes les tables connues de Base si elles n'existent pas encore.
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Watchlist Backend", version="0.1.0")

app.include_router(watched.router)


@app.get("/health")
def health_check() -> dict[str, str]:
    """Endpoint simple pour vérifier que l'API répond."""
    return {"status": "ok"}
