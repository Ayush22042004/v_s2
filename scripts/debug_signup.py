import os, sys
# Ensure project root is on sys.path so `from app import app` works when this script is run directly
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from init_sqlite_db import init_db
from app import app
import sqlite3

init_db()
client = app.test_client()
# perform signup
resp = client.post('/candidate_signup', data={'name':'Debug Cand','email':'debug@example.com','username':'debugcand','password':'dpass','category':'General'}, follow_redirects=True)
print('signup status', resp.status_code)
DB = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'voting.db'))
conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row
cur = conn.cursor()
print('USERS:')
for r in cur.execute('SELECT id,username,role FROM users'):
    print(dict(r))
print('APPS:')
try:
    for r in cur.execute('SELECT id,user_id,election_id,name,status,applied_at FROM candidate_applications'):
        print(dict(r))
except Exception as e:
    print('err', e)
cur.close(); conn.close()
