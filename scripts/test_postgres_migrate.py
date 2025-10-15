"""Small helper to test Postgres migrations locally.

Usage (PowerShell):
  # start postgres: docker-compose up -d
  $env:DATABASE_URL='postgres://vsuser:vsPass@localhost:5432/vsdb'
  python .\scripts\test_postgres_migrate.py
"""
import os
import db_pg

if __name__ == '__main__':
    url = os.environ.get('DATABASE_URL')
    if not url:
        print('Set DATABASE_URL environment variable first')
        raise SystemExit(1)
    print('Running migrations against', url)
    db_pg.migrate_and_seed()
    print('Migrations completed')
