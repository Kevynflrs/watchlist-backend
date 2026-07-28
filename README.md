# Watchlist Backend

![CI](https://img.shields.io/badge/CI-pending-lightgrey)
![License](https://img.shields.io/badge/license-MIT-blue)
![Python](https://img.shields.io/badge/python-3.11-blue)

API backend pour un système personnel de recommandation de films, croisant mon
historique [Letterboxd](https://letterboxd.com) avec un catalogue construit
depuis [TMDB](https://www.themoviedb.org).

## Pourquoi ce projet

Après quelques années à utiliser Letterboxd pour noter les films vus, réexporter
et retraiter manuellement mon historique à chaque envie de nouvelles recommandations
devenait fastidieux et surtout risquait de dupliquer des films à chaque réimport.

Ce backend résout deux problèmes concrets :
- **Réimporter tout l'historique Letterboxd sans jamais dupliquer** (upsert par
  clé `titre_année`), pour ne pas avoir à trier "nouveaux films only" à la main.
- **Construire un catalogue pertinent directement depuis l'API TMDB** (pas un
  gros CSV Kaggle figé), filtré sur les films ayant assez de votes pour être
  fiables en recommandation.

Au-delà de l'usage personnel, ce projet sert de démonstration concrète de
compétences backend, ML et DevOps : API REST typée, pipeline scikit-learn
persisté, tests à plusieurs niveaux (unitaire, intégration, end-to-end),
CI, conteneurisation.

## Architecture

```
watchlist-backend (ce repo) --> API FastAPI, DB, pipeline ML, intégration TMDB
watchlist-frontend --> interface Streamlit ("Netflix de ma watchlist")
watchlist (méta-repo) --> README d'architecture, docker-compose global, notebook Colab
```

```
watchlist-backend/
├── .github/
│   └── workflows/
│       └── ci.yml # lint + tests à chaque push/PR (main, develop)
├── app/
│   ├── main.py # point d'entrée FastAPI
│   ├── config.py # config centralisée (env vars)
│   ├── database.py # engine SQLAlchemy, session, Base
│   ├── models_db.py # modèles ORM : Movie, WatchedMovie
│   ├── schemas.py # schémas Pydantic (contrats API)
│   ├── ml_core.py # nettoyage : match_key, genres, catalogue
│   ├── features.py # feature engineering (FeatureBundle)
│   ├── train.py # entraînement + persistance (ModelBundle)
│   ├── scoring.py # scoring du catalogue, catégorisation
│   ├── imports.py # upsert des imports Letterboxd
│   ├── tmdb_client.py # client TMDB synchrone
│   ├── tmdb_async_client.py # client TMDB asynchrone (sync catalogue, exclusion des connus)
│   ├── tmdb_csv_import.py # parsing d'un export CSV TMDB (format pivot normalisé)
│   └── routers/
│       ├── watched.py # POST /watched/import/*, GET /watched/
│       ├── catalogue.py # POST /catalogue/sync, /import, /enrich, /stats
│       ├── train.py # POST /train/, GET /train/status
│       ├── recommend.py # GET /recommend/
│       └── categories.py # GET /recommend/categories
├── tests/
│   ├── test_models_db.py
│   ├── test_ml_core.py
│   ├── test_features.py
│   ├── test_train.py
│   ├── test_scoring.py
│   ├── test_pipeline_integration.py
│   ├── test_imports.py
│   ├── test_import_endpoints.py
│   ├── test_tmdb_client.py
│   ├── test_tmdb_async_client.py
│   ├── test_tmdb_respx.py
│   ├── test_tmdb_csv_import.py
│   ├── test_tmdb_sync_exclusion.py
│   └── test_e2e_scenario.py
├── scripts/ # scripts ponctuels (imports manuels, debug)
├── data/ # DB SQLite locale (généré, ignoré par git)
├── models/ # modèle .joblib (généré, ignoré par git)
├── .env.example
├── .env
├── .gitignore
├── .dockerignore
├── .pre-commit-config.yaml
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml # config black + ruff
├── requirements.txt # dépendances de prod
├── requirements-dev.txt # dépendances de dev (pytest, black, ruff...)
├── LICENSE
└── README.md
```

**Pipeline ML** : genres one-hot (`MultiLabelBinarizer`) + note moyenne / nb de
votes / année / durée / revenu (scalés via `MinMaxScaler`) --> `RandomForestClassifier`
--> modèle persisté sur disque (`joblib`), jamais réentraîné à chaque appel.

## Installation

### Avec Docker (recommandé)

```bash
git clone https://github.com/Kevynflrs/watchlist-backend.git
cd watchlist-backend
cp .env.example .env # renseigner TMDB_API_KEY / TMDB_BEARER_TOKEN
docker compose up --build
```

L'API est disponible sur `http://localhost:8000`, la documentation interactive
sur `http://localhost:8000/docs`.

### En local (sans Docker)

```bash
git clone https://github.com/Kevynflrs/watchlist-backend.git
cd watchlist-backend
python -m venv .venv
source .venv\Scripts\Activate.ps1 # ou .venv/bin/activate sous Linux
pip install -r requirements.txt -r requirements-dev.txt
cp .env.example .env # renseigner TMDB_API_KEY / TMDB_BEARER_TOKEN
uvicorn app.main:app --reload
```

## Endpoints

| Méthode | Route | Description |
|---|---|---|
| `GET` | `/health` | Vérifie que l'API répond |
| `POST` | `/watched/import/watched` | Importe un `watched.csv` Letterboxd (films vus) |
| `POST` | `/watched/import/ratings` | Importe un `ratings.csv` Letterboxd (films notés) |
| `GET` | `/watched/` | Liste les films vus en DB |
| `POST` | `/catalogue/sync` | Construit/actualise le catalogue depuis TMDB (exclut les films déjà connus) |
| `POST` | `/catalogue/import` | Importe/complète le catalogue depuis un CSV TMDB local |
| `POST` | `/catalogue/enrich` | Complète les films incomplets du catalogue |
| `GET` | `/catalogue/stats` | Statistiques sur le catalogue (total, champs manquants) |
| `POST` | `/train/` | Entraîne le modèle sur les données actuelles |
| `GET` | `/train/status` | État et métriques du dernier modèle entraîné |
| `GET` | `/recommend/` | Retourne les films recommandés, non-vus, triés par score |
| `GET` | `/recommend/categories` | Liste les catégories de style disponibles |

Exemples de requêtes :

```bash
curl -X POST http://localhost:8000/watched/import/ratings \
  -F "file=@ratings.csv"
```

```bash
curl -X POST "http://localhost:8000/catalogue/import?fill_missing_only=true" \
  -F "file=@tmdb_movies.csv"
```

Documentation interactive complète (Swagger UI) : `http://localhost:8000/docs`.

## Tests

```bash
pytest # suite complète
pytest --cov=app --cov-report=term-missing # avec couverture
```

- Tests unitaires : nettoyage de données, feature engineering, scoring, upsert
- Tests d'intégration : endpoints via `TestClient`, TMDB mocké avec `respx`
- Tests end-to-end : scénario complet import --> entraînement --> recommandation

![Coverage](https://img.shields.io/badge/coverage-90%25-brightgreen)

## Stack technique

FastAPI · SQLAlchemy · PostgreSQL/SQLite · scikit-learn · pandas · httpx ·
pytest · Docker · GitHub Actions

## Repos liés

- [watchlist-frontend](https://github.com/Kevynflrs/watchlist-frontend) : interface Streamlit
- [watchlist](https://github.com/Kevynflrs/watchlist) : méta-repo (architecture globale, docker-compose, notebook Colab)

## Convention de commits

Ce projet suit [Conventional Commits](https://www.conventionalcommits.org/) :

```
<type>: <description>
```

**Types utilisés dans ce projet :**

| Type | Usage |
|---|---|
| `feat` | Nouvelle fonctionnalité (ex: nouvel endpoint, nouvelle feature ML) |
| `fix` | Correction de bug |
| `test` | Ajout ou modification de tests, sans changement de comportement |
| `docs` | Documentation uniquement (README, docstrings) |
| `refactor` | Changement de code sans nouvelle fonctionnalité ni correction de bug |

## Licence

Ce projet est sous licence [MIT](./LICENSE).
