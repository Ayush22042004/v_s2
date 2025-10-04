import os, bcrypt
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import psycopg2, psycopg2.extras

IST = ZoneInfo("Asia/Kolkata")

def get_conn():
    dsn = os.environ.get("DATABASE_URL", "").strip()
    if not dsn:
        raise RuntimeError("DATABASE_URL is not set.")
    if "sslmode" not in dsn:
        dsn += ("&" if "?" in dsn else "?") + "sslmode=require"
    return psycopg2.connect(dsn, cursor_factory=psycopg2.extras.RealDictCursor)

def exec_sql(sql, params=None, fetch=False, one=False):
    conn = get_conn()
    try:
        with conn, conn.cursor() as cur:
            cur.execute(sql, params or ())
            if fetch:
                return (cur.fetchone() if one else cur.fetchall())
    finally:
        conn.close()

def migrate_and_seed():
    # Schema
    exec_sql("""
        CREATE TABLE IF NOT EXISTS users(
          id SERIAL PRIMARY KEY,
          username TEXT UNIQUE NOT NULL,
          password_hash BYTEA NOT NULL,
          role TEXT NOT NULL DEFAULT 'voter'
        );
    """)
    exec_sql("""
        CREATE TABLE IF NOT EXISTS elections(
          id SERIAL PRIMARY KEY,
          title TEXT,
          category TEXT,
          year INT,
          start_time TIMESTAMPTZ NOT NULL,
          end_time TIMESTAMPTZ NOT NULL,
          candidate_limit INT
        );
    """)
    exec_sql("""
        CREATE TABLE IF NOT EXISTS candidates(
          id SERIAL PRIMARY KEY,
          election_id INT REFERENCES elections(id) ON DELETE CASCADE,
          name TEXT NOT NULL
        );
    """)
    exec_sql("""
        CREATE TABLE IF NOT EXISTS votes(
          id SERIAL PRIMARY KEY,
          election_id INT REFERENCES elections(id) ON DELETE CASCADE,
          candidate_id INT REFERENCES candidates(id) ON DELETE CASCADE,
          voter_id INT REFERENCES users(id) ON DELETE SET NULL,
          created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
    """)
    # Seed admin
    row = exec_sql("SELECT id FROM users WHERE username=%s", ("admin",), fetch=True, one=True)
    if not row:
        hashed = bcrypt.hashpw(b"admin123", bcrypt.gensalt())
        exec_sql("INSERT INTO users(username, password_hash, role) VALUES(%s,%s,'admin')",
                 ("admin", hashed))

def parse_ist_local_to_utc(dt_local_str: str):
    dt = datetime.fromisoformat(dt_local_str)  # 'YYYY-MM-DDTHH:MM'
    return dt.replace(tzinfo=IST).astimezone(timezone.utc)

def now_utc():
    return datetime.now(timezone.utc)

def install_jinja_filters(app):
    @app.template_filter("istfmt")
    def istfmt(value):
        if not value: return ""
        dt = value
        if isinstance(value, str):
            try:
                dt = datetime.fromisoformat(value.replace("Z",""))
            except Exception:
                return value
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(IST).strftime("%d %b %Y, %I:%M %p IST")
    return app