from app import app
import os
import sys
sys.path.append(os.path.dirname(__file__))
from init_sqlite_db import init_db

# Quick smoke test using Flask test client

def run_smoke():
    # initialize local sqlite DB (creates all tables)
    init_db()
    client = app.test_client()
    r = client.get('/')
    print('GET / ->', r.status_code)
    r = client.get('/signup')
    print('GET /signup ->', r.status_code)
    r = client.get('/admin')
    print('GET /admin ->', r.status_code, 'Location:', r.headers.get('Location'))
    # attempt admin login via POST
    r = client.post('/login', data={'username':'admin','password':'admin123'}, follow_redirects=False)
    print('POST /login ->', r.status_code, 'Location:', r.headers.get('Location'))
    # candidate signup (use unique username to avoid collisions)
    import uuid
    cand_username = 'smokecand_' + uuid.uuid4().hex[:8]
    cand_email = f"{cand_username}@example.com"
    # cleanup any previous test data
    DB = os.path.join(os.path.dirname(__file__), '..', 'voting.db')
    DB = os.path.abspath(DB)
    conn = None
    try:
        conn = __import__('sqlite3').connect(DB)
        cur = conn.cursor()
        # find existing user id
        cur.execute('SELECT id FROM users WHERE username=?', (cand_username,))
        row = cur.fetchone()
        if row:
            uid = row[0]
            cur.execute('DELETE FROM candidate_applications WHERE user_id=?', (uid,))
            cur.execute('DELETE FROM candidates WHERE user_id=?', (uid,))
            cur.execute('DELETE FROM users WHERE id=?', (uid,))
            conn.commit()
        cur.close()
    except Exception:
        pass
    finally:
        if conn:
            conn.close()

    data = {'name':'Smoke Cand','email':cand_email,'username':cand_username,'password':'pass123','category':'General'}
    r = client.post('/candidate_signup', data=data, follow_redirects=True)
    print('POST /candidate_signup ->', r.status_code, 'username=', cand_username)
    # confirm application exists in DB (retry a few times in case of commit/IO delay)
    import sqlite3, time
    DB = os.path.join(os.path.dirname(__file__), '..', 'voting.db')
    DB = os.path.abspath(DB)
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    app_row = None
    for attempt in range(5):
        cur.execute("SELECT id, user_id, status FROM candidate_applications WHERE user_id=(SELECT id FROM users WHERE username=?)", (cand_username,))
        app_row = cur.fetchone()
        if app_row:
            break
        print('Waiting for application to appear in DB... (attempt', attempt+1, ')')
        time.sleep(0.2)
    if not app_row:
        print('FAIL: application row not found after retries')
        cur.close(); conn.close(); return
    app_id = app_row['id']
    print('Found application id=', app_id, 'status=', app_row['status'])
    # login as admin and approve the application via endpoint
    client.post('/login', data={'username':'admin','password':'admin123'}, follow_redirects=True)
    r = client.post('/admin/approve_candidate', data={'application_id': str(app_id)}, follow_redirects=True)
    print('POST /admin/approve_candidate ->', r.status_code)
    # verify application status updated and candidate row exists
    cur.execute('SELECT status, candidate_id FROM candidate_applications WHERE id=?', (app_id,))
    updated = cur.fetchone()
    if updated and updated['status'] == 'approved' and updated['candidate_id']:
        cand_id = updated['candidate_id']
        cur.execute('SELECT * FROM candidates WHERE id=?', (cand_id,))
        cand = cur.fetchone()
        if cand and cand['user_id']:
            print('PASS: application approved and candidate created (id=', cand_id, ')')
        else:
            print('FAIL: candidate row not found or missing user_id')
    else:
        print('FAIL: application not approved or candidate_id missing; row=', dict(updated) if updated else None)
    cur.close(); conn.close()

if __name__ == '__main__':
    run_smoke()
