import sqlite3, os
DB = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'voting.db'))
print('DB:', DB)
conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row
cur = conn.cursor()
print('\nUSERS:')
for r in cur.execute('SELECT id, username, role FROM users'):
    print(dict(r))
print('\nAPPLICATIONS:')
try:
    for r in cur.execute('SELECT id,user_id,election_id,name,status,applied_at FROM candidate_applications'):
        print(dict(r))
except Exception as e:
    print('Error reading applications table:', e)
cur.close(); conn.close()
