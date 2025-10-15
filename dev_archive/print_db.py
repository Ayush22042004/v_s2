import sqlite3, os
DB = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'voting.db'))
conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row
cur = conn.cursor()
for tbl in ['users','elections','candidates','candidate_applications','notifications']:
    try:
        print('==', tbl)
        for r in cur.execute(f'SELECT * FROM {tbl} LIMIT 5'):
            print(dict(r))
    except Exception as e:
        print('skip', tbl, e)
cur.close(); conn.close()
