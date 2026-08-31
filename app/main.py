from fastapi import FastAPI

from app.database import Base, engine, ensure_recommendation_columns
from app.routers import catalogue, categories, recommend, train, watched

# Crée toutes les tables connues de Base si elles n'existent pas encore.
Base.metadata.create_all(bind=engine)
ensure_recommendation_columns(engine)

app = FastAPI(title="Watchlist Backend", version="0.1.1")

app.include_router(watched.router)
app.include_router(catalogue.router)
app.include_router(train.router)
app.include_router(recommend.router)
app.include_router(categories.router)


@app.get("/health")
def health_check() -> dict[str, str]:
    """Endpoint simple pour vérifier que l'API répond."""
    return {"status": "ok"}
