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
