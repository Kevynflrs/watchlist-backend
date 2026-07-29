"""
Import en masse d'un gros CSV TMDB directement en DB, sans passer par l'API HTTP.

Lit le fichier par lots, et réutilise exactement la même logique d'upsert que l'endpoint POST /catalogue/import.

Usage (depuis la racine du repo, venv activé) :

    $env:DATABASE_URL = "postgresql://watchlist:watchlist@localhost:5432/watchlist" \\
        python scripts/bulk_import_tmdb_csv.py chemin/vers/tmdb_movies.csv
"""

import argparse
import sys
import time
from pathlib import Path

# Permet d'importer les modules app.* en lançant ce script directement, sans avoir besoin d'installer le projet comme un package.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.routers.catalogue import _upsert_movies
from app.tmdb_csv_import import iter_tmdb_csv_chunks


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Importe un gros CSV TMDB directement en DB, par lots."
    )
    parser.add_argument("csv_path", help="Chemin vers le fichier CSV TMDB à importer")
    parser.add_argument(
        "--database-url",
        default=None,
        help="URL de connexion DB (sinon lue depuis la variable d'env DATABASE_URL)",
    )
    parser.add_argument(
        "--chunksize", type=int, default=5000, help="Nombre de lignes lues par lot (défaut: 5000)"
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Écrase les champs déjà remplis en DB (défaut : ne comble que les champs vides)",
    )
    args = parser.parse_args()

    database_url = args.database_url or __import__("os").getenv("DATABASE_URL")
    if not database_url:
        print("Erreur : fournis --database-url ou définis la variable d'env DATABASE_URL.")
        sys.exit(1)

    fill_missing_only = not args.overwrite

    engine = create_engine(database_url)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    totals = {"inserted": 0, "updated": 0, "unchanged": 0, "skipped_duplicates": 0}
    start = time.time()

    try:
        for i, chunk in enumerate(
            iter_tmdb_csv_chunks(args.csv_path, chunksize=args.chunksize), start=1
        ):
            summary = _upsert_movies(session, chunk, fill_missing_only=fill_missing_only)
            for key in totals:
                totals[key] += summary[key]

            elapsed = time.time() - start
            print(
                f"[lot {i}] {len(chunk)} lignes — "
                f"inserted={summary['inserted']} updated={summary['updated']} "
                f"unchanged={summary['unchanged']} "
                f"skipped_duplicates={summary['skipped_duplicates']} "
                f"(écoulé: {elapsed:.0f}s)"
            )
    finally:
        session.close()

    print("\n Résumé final")
    for key, value in totals.items():
        print(f"{key}: {value}")
    print(f"Temps total : {time.time() - start:.0f}s")


if __name__ == "__main__":
    main()
