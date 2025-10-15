from datetime import datetime, timezone

def parse_utc_iso(dt_str):
    if not dt_str:
        return None
    # Accept ...Z or +00:00
    return datetime.fromisoformat(dt_str.replace('Z','+00:00'))

import os
import psycopg
from psycopg.rows import dict_row
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")

def get_conn():
    dsn = os.environ.get("DATABASE_URL","").strip()
    if not dsn: raise RuntimeError("DATABASE_URL is not set.")
    if "sslmode" not in dsn: dsn += ("&" if "?" in dsn else "?") + "sslmode=require"
    return psycopg.connect(dsn, row_factory=dict_row)

def exec_sql(sql, params=None, fetch=False, one=False):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params or ())
            if fetch: return cur.fetchone() if one else cur.fetchall()

def now_utc(): return datetime.now(timezone.utc)

def parse_ist_local_to_utc(dt_str):
    local_dt = datetime.fromisoformat(dt_str)
    ist_dt = local_dt.replace(tzinfo=IST)
    return ist_dt.astimezone(timezone.utc)

def install_jinja_filters(app):
    @app.template_filter("istfmt")
    def istfmt(value):
        if not value: return ""
        try:
            dt = value
            if isinstance(dt, str): dt = datetime.fromisoformat(dt.replace("Z",""))
            if dt.tzinfo is None: dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(IST).strftime("%d %b %Y, %I:%M %p IST")
        except Exception: return value
    return app

def migrate_and_seed():
    schema = '''
        CREATE TABLE IF NOT EXISTS users(
            id SERIAL PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL CHECK (role IN ('admin','voter','candidate')),
            name TEXT,
            email TEXT,
            id_number TEXT
        );
    CREATE TABLE IF NOT EXISTS elections(
      id SERIAL PRIMARY KEY, title TEXT NOT NULL, year INTEGER, category TEXT NOT NULL,
      start_time TIMESTAMPTZ NOT NULL, end_time TIMESTAMPTZ NOT NULL, created_by INTEGER,
      candidate_limit INTEGER,
      FOREIGN KEY(created_by) REFERENCES users(id) ON DELETE SET NULL
    );
        CREATE TABLE IF NOT EXISTS candidates(
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            photo TEXT,
            election_id INTEGER REFERENCES elections(id) ON DELETE CASCADE,
            user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
            votes INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS candidate_applications(
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            election_id INTEGER REFERENCES elections(id) ON DELETE SET NULL,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            photo TEXT,
            status TEXT NOT NULL CHECK (status IN ('pending','approved','rejected')) DEFAULT 'pending',
            applied_at TIMESTAMPTZ,
            approved_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
            approved_at TIMESTAMPTZ,
            candidate_id INTEGER REFERENCES candidates(id) ON DELETE SET NULL
        );
    CREATE TABLE IF NOT EXISTS votes(
      id SERIAL PRIMARY KEY, voter_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
      candidate_id INTEGER REFERENCES candidates(id) ON DELETE CASCADE,
      election_id INTEGER REFERENCES elections(id) ON DELETE CASCADE, UNIQUE(voter_id, election_id)
    );
        CREATE TABLE IF NOT EXISTS notifications(
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            message TEXT NOT NULL,
            created_at TIMESTAMPTZ,
            read BOOLEAN DEFAULT FALSE
        );
    '''
    exec_sql(schema)
    row = exec_sql("SELECT id FROM users WHERE username=%s", ("admin",), fetch=True, one=True)
    if not row:
        exec_sql("INSERT INTO users(username,password,role) VALUES(%s,%s,%s)", ("admin","admin123","admin"))
    print("✅ Migration complete")
    try:
        exec_sql("CREATE UNIQUE INDEX IF NOT EXISTS ux_app_user_election ON candidate_applications(user_id, election_id)", fetch=False)
    except Exception:
        pass
