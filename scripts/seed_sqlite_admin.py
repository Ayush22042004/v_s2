import sqlite3
from werkzeug.security import generate_password_hash
import os

DB = os.path.join(os.path.dirname(__file__), '..', 'voting.db')
DB = os.path.abspath(DB)

def ensure_admin():
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users(
      id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE NOT NULL, password TEXT NOT NULL, role TEXT NOT NULL, name TEXT, email TEXT, id_number TEXT
    )
    """)
    cur.execute("SELECT id FROM users WHERE username=?", ('admin',))
    if not cur.fetchone():
        pw = generate_password_hash('admin123')
        cur.execute("INSERT INTO users(username,password,role,name) VALUES (?,?,?,?)", ('admin', pw, 'admin', 'Administrator'))
        conn.commit()
        print('Inserted admin user (username=admin, password=admin123)')
    else:
        print('Admin user already exists')
    cur.close()
    conn.close()

if __name__ == '__main__':
    ensure_admin()
