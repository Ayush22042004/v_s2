import sqlite3
import os
from werkzeug.security import generate_password_hash

DB = os.path.join(os.path.dirname(__file__), '..', 'voting.db')
DB = os.path.abspath(DB)

SCHEMA = '''
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS users(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  username TEXT UNIQUE NOT NULL,
  password TEXT NOT NULL,
  role TEXT NOT NULL CHECK(role IN ('admin','voter','candidate')),
  name TEXT,
  email TEXT,
  id_number TEXT
);
CREATE TABLE IF NOT EXISTS elections(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  title TEXT NOT NULL,
  year INTEGER,
  category TEXT NOT NULL,
  start_time TEXT NOT NULL,
  end_time TEXT NOT NULL,
  created_by INTEGER,
  candidate_limit INTEGER,
  FOREIGN KEY(created_by) REFERENCES users(id) ON DELETE SET NULL
);
CREATE TABLE IF NOT EXISTS candidates(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  category TEXT NOT NULL,
  photo TEXT,
  election_id INTEGER,
  user_id INTEGER,
  votes INTEGER DEFAULT 0,
  FOREIGN KEY(election_id) REFERENCES elections(id) ON DELETE CASCADE
  ,FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE SET NULL
);
CREATE TABLE IF NOT EXISTS candidate_applications(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL,
  election_id INTEGER,
  name TEXT NOT NULL,
  category TEXT NOT NULL,
  photo TEXT,
  status TEXT NOT NULL CHECK(status IN ('pending','approved','rejected')) DEFAULT 'pending',
  applied_at TEXT,
  approved_by INTEGER,
  approved_at TEXT,
  candidate_id INTEGER,
  FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
  FOREIGN KEY(election_id) REFERENCES elections(id) ON DELETE SET NULL,
  FOREIGN KEY(approved_by) REFERENCES users(id) ON DELETE SET NULL,
  FOREIGN KEY(candidate_id) REFERENCES candidates(id) ON DELETE SET NULL
);
CREATE TABLE IF NOT EXISTS votes(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  voter_id INTEGER,
  candidate_id INTEGER,
  election_id INTEGER,
  timestamp TEXT,
  UNIQUE(voter_id, election_id),
  FOREIGN KEY(voter_id) REFERENCES users(id) ON DELETE CASCADE,
  FOREIGN KEY(candidate_id) REFERENCES candidates(id) ON DELETE CASCADE,
  FOREIGN KEY(election_id) REFERENCES elections(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS notifications(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL,
  message TEXT NOT NULL,
  created_at TEXT,
  read INTEGER DEFAULT 0,
  FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
);
'''

def init_db():
    os.makedirs(os.path.dirname(DB), exist_ok=True)
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    cur.executescript(SCHEMA)
    # ensure admin
    cur.execute("SELECT id FROM users WHERE username=?", ('admin',))
    if not cur.fetchone():
        pw = generate_password_hash('admin123')
        cur.execute("INSERT INTO users(username,password,role,name) VALUES (?,?,?,?)", ('admin', pw, 'admin', 'Administrator'))
        print('Inserted admin user (username=admin, password=admin123)')
    else:
        print('Admin user already exists')
    conn.commit()
    cur.close()
    conn.close()
    # ensure unique constraint/index for (user_id, election_id)
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    try:
        cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS ux_app_user_election ON candidate_applications(user_id, election_id);")
    except Exception:
        pass
    conn.commit()
    cur.close()
    conn.close()
    # ensure candidates table has user_id column (for migrations from older DBs)
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    try:
        cur.execute("PRAGMA table_info(candidates)")
        cols = [r[1] for r in cur.fetchall()]
        if 'user_id' not in cols:
            try:
                cur.execute('ALTER TABLE candidates ADD COLUMN user_id INTEGER')
                conn.commit()
            except Exception:
                pass
    except Exception:
        pass
    cur.close(); conn.close()

if __name__ == '__main__':
    init_db()
