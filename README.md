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
```

**Pipeline ML** : genres one-hot (`MultiLabelBinarizer`) + note moyenne / nb de
votes / année / durée / revenu (scalés via `MinMaxScaler`) --> `RandomForestClassifier`
--> modèle persisté sur disque (`joblib`), jamais réentraîné à chaque appel.

## Installation

### Avec Docker (recommandé)

```bash
git clone https://github.com/<ton-user>/watchlist-backend.git
cd watchlist-backend
cp .env.example .env # renseigner TMDB_API_KEY / TMDB_BEARER_TOKEN
docker compose up --build
```

L'API est disponible sur `http://localhost:8000`, la documentation interactive
sur `http://localhost:8000/docs`.

### En local (sans Docker)

```bash
git clone https://github.com/<ton-user>/watchlist-backend.git
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
| `POST` | `/catalogue/sync` | Construit/actualise le catalogue depuis TMDB |
| `POST` | `/catalogue/enrich` | Complète les films incomplets du catalogue |
| `POST` | `/train/` | Entraîne le modèle sur les données actuelles |
| `GET` | `/train/status` | État et métriques du dernier modèle entraîné |
| `GET` | `/recommend/` | Retourne les films recommandés, non-vus, triés par score |
| `GET` | `/recommend/categories` | Liste les catégories de style disponibles |

Exemple de requête :

```bash
curl -X POST http://localhost:8000/watched/import/ratings \
  -F "file=@ratings.csv"
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

- [watchlist-frontend](https://github.com/<ton-user>/watchlist-frontend) --> interface Streamlit
- [watchlist](https://github.com/<ton-user>/watchlist) --> méta-repo (architecture globale, docker-compose, notebook Colab)

## Licence

Ce projet est sous licence [MIT](./LICENSE).
