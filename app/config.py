import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

# Base de données
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'data' / 'watchlist.db'}")

# TMDB
# Le Bearer token (v4) est la méthode d'authentification recommandée par TMDB,
# mais on garde l'api_key (v3) en fallback pour rester compatible avec les deux.
TMDB_API_KEY = os.getenv("TMDB_API_KEY", "")
TMDB_BEARER_TOKEN = os.getenv("TMDB_BEARER_TOKEN", "")

TMDB_API_BASE = "https://api.themoviedb.org/3"
TMDB_IMAGE_BASE = "https://image.tmdb.org/t/p/w500"

# Modèle ML
MODEL_PATH = BASE_DIR / "models" / "model_bundle.joblib"

# Création automatique des dossiers nécessaires
(BASE_DIR / "data").mkdir(exist_ok=True)
(BASE_DIR / "models").mkdir(exist_ok=True)
