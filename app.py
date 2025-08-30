
import os
import sqlite3
from datetime import datetime, timezone
from functools import wraps

from flask import (
    Flask, render_template, request, redirect, url_for,
    flash, session
)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

APP_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("DB_PATH", os.path.join(APP_DIR, "voting.db"))

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-key")

# ---------------- DB Helpers ----------------
def get_db():
    db = getattr(app, "_db", None)
    if db is None:
        db = sqlite3.connect(DB_PATH, check_same_thread=False)
        db.row_factory = sqlite3.Row
        app._db = db
    return db

def query(sql, args=(), one=False):
    cur = get_db().execute(sql, args)
    rows = cur.fetchall()
    cur.close()
    return (rows[0] if rows else None) if one else rows

def execute(sql, args=()):
    db = get_db()
    cur = db.execute(sql, args)
    db.commit()
    return cur.lastrowid

# -------------- Schema & Migrations --------------
def ensure_schema():
    db = get_db()
    db.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT UNIQUE,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        role TEXT NOT NULL,
        id_number TEXT
    )
    """)
    db.execute("""
    CREATE TABLE IF NOT EXISTS elections (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT,
        year INTEGER,
        category TEXT NOT NULL,
        start_time TEXT NOT NULL,
        end_time TEXT NOT NULL,
        created_by INTEGER,
        candidate_limit INTEGER
    )
    """)
    db.execute("""
    CREATE TABLE IF NOT EXISTS candidates (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        category TEXT,
        photo TEXT,
        election_id INTEGER,
        FOREIGN KEY (election_id) REFERENCES elections(id)
    )
    """)
    db.execute("""
    CREATE TABLE IF NOT EXISTS votes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        voter_id INTEGER NOT NULL,
        candidate_id INTEGER NOT NULL,
        election_id INTEGER NOT NULL,
        timestamp TEXT NOT NULL,
        FOREIGN KEY (voter_id) REFERENCES users(id),
        FOREIGN KEY (candidate_id) REFERENCES candidates(id),
        FOREIGN KEY (election_id) REFERENCES elections(id)
    )
    """)

    # Migrate columns if missing
    cols = {r[1] for r in query("PRAGMA table_info(elections)")}
    if "title" not in cols:
        db.execute("ALTER TABLE elections ADD COLUMN title TEXT")
    if "year" not in cols:
        db.execute("ALTER TABLE elections ADD COLUMN year INTEGER")
    if "created_by" not in cols:
        db.execute("ALTER TABLE elections ADD COLUMN created_by INTEGER")
    if "candidate_limit" not in cols:
        db.execute("ALTER TABLE elections ADD COLUMN candidate_limit INTEGER")

    c_cols = {r[1] for r in query("PRAGMA table_info(candidates)")}
    if "election_id" not in c_cols:
        db.execute("ALTER TABLE candidates ADD COLUMN election_id INTEGER")

    # Unique index to prevent double-voting
    db.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_votes_unique ON votes(voter_id, election_id)")
    db.commit()

def seed_admin():
    admin = query("SELECT id FROM users WHERE role='admin' LIMIT 1", one=True)
    if not admin:
        execute(
            "INSERT INTO users (name, email, username, password, role) VALUES (?,?,?,?,?)",
            ("Admin", "admin@example.com", "admin", generate_password_hash("admin123"), "admin")
        )

# Boot for Flask 3.x (no before_first_request)
with app.app_context():
    ensure_schema()
    seed_admin()

# -------------- Auth helpers --------------
def login_required(role=None):
    def deco(f):
        @wraps(f)
        def wrap(*args, **kwargs):
            if "user_id" not in session:
                flash("Please login first.", "warn")
                return redirect(url_for("login"))
            if role and session.get("role") != role:
                flash("Not authorized.", "error")
                return redirect(url_for("index"))
            return f(*args, **kwargs)
        return wrap
    return deco

# -------------- Time helpers --------------
def parse_iso(s):
    try:
        dt = datetime.fromisoformat((s or "").replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None

def normalize_local(s):
    s = (s or "").strip()
    if not s:
        return s
    # 'YYYY-MM-DDTHH:MM' -> add seconds + Z (assume UTC)
    if "Z" not in s and "+" not in s:
        if len(s) == 16:
            return s + ":00Z"
        if len(s) == 19 and s.count(":") == 2:
            return s + "Z"
    return s

def now_utc():
    return datetime.now(timezone.utc)

# -------------- Routes --------------
@app.route("/")
def index():
    user = None
    if "user_id" in session:
        user = query("SELECT * FROM users WHERE id=?", (session["user_id"],), one=True)
    active = query("SELECT * FROM elections ORDER BY start_time DESC LIMIT 5")
    return render_template("index.html", user=user, elections=active)

@app.route("/signup", methods=["GET","POST"])
def signup():
    if request.method == "POST":
        name = request.form.get("name","").strip()
        email = request.form.get("email","").strip().lower() or None
        username = request.form.get("username","").strip().lower()
        password = request.form.get("password","")
        id_number = request.form.get("id_number","").strip()

        if not name or not username or not password or not id_number:
            flash("All fields except email are required.", "error")
            return redirect(url_for("signup"))

        existing_user = query("SELECT id FROM users WHERE lower(username)=?", (username,), one=True)
        if existing_user:
            flash("Username already taken.", "error")
            return redirect(url_for("signup"))
        if email:
            existing_email = query("SELECT id FROM users WHERE lower(email)=?", (email,), one=True)
            if existing_email:
                flash("Email already registered.", "error")
                return redirect(url_for("signup"))

        execute(
            "INSERT INTO users (name,email,username,password,role,id_number) VALUES (?,?,?,?,?,?)",
            (name, email, username, generate_password_hash(password), "voter", id_number)
        )
        flash("Account created. Please login.", "ok")
        return redirect(url_for("login"))
    return render_template("signup.html")

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username","").strip().lower()
        password = request.form.get("password","")
        user = query("SELECT * FROM users WHERE lower(username)=?", (username,), one=True)
        if user and check_password_hash(user["password"], password):
            session["user_id"] = user["id"]
            session["role"]   = user["role"]
            flash("Welcome back!", "ok")
            return redirect(url_for("index"))
        flash("Invalid credentials.", "error")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out.", "ok")
    return redirect(url_for("index"))

# ----------- Admin Dashboard -----------
@app.route("/admin")
@login_required(role="admin")
def admin():
    own_elections = query(
        "SELECT * FROM elections WHERE created_by=? ORDER BY start_time DESC",
        (session.get("user_id"),)
    )
    candidates = query("""
        SELECT c.*, e.title as e_title, e.candidate_limit as e_limit
        FROM candidates c
        LEFT JOIN elections e ON e.id=c.election_id
        WHERE e.created_by = ? OR e.created_by IS NULL
        ORDER BY c.id DESC
    """, (session.get("user_id"),))
    return render_template("admin.html", elections=own_elections, candidates=candidates)

@app.route("/add_candidate", methods=["POST"])
@login_required(role="admin")
def add_candidate():
    name = request.form.get("name","").strip()
    category = request.form.get("category","").strip() or "General"
    election_id = request.form.get("election_id","").strip()
    if not name or not election_id:
        flash("Candidate name and election are required.", "error")
        return redirect(url_for("admin"))
    try:
        election_id = int(election_id)
    except ValueError:
        flash("Invalid election selected.", "error")
        return redirect(url_for("admin"))

    e = query("SELECT id, candidate_limit, created_by FROM elections WHERE id=?", (election_id,), one=True)
    if not e:
        flash("Selected election does not exist.", "error")
        return redirect(url_for("admin"))
    if e["created_by"] and e["created_by"] != session.get("user_id"):
        flash("You can only add candidates to your own elections.", "error")
        return redirect(url_for("admin"))

    if e["candidate_limit"] is not None:
        count_row = query("SELECT COUNT(*) as c FROM candidates WHERE election_id=?", (election_id,), one=True)
        if count_row and count_row["c"] >= e["candidate_limit"]:
            flash("Candidate limit reached for this election.", "warn")
            return redirect(url_for("admin"))

    photo_path = None
    f = request.files.get("photo")
    if f and f.filename:
        filename = secure_filename(f.filename)
        uploads_dir = os.path.join(APP_DIR, "static", "uploads")
        os.makedirs(uploads_dir, exist_ok=True)
        full = os.path.join(uploads_dir, filename)
        f.save(full)
        photo_path = f"uploads/{filename}"

    execute("INSERT INTO candidates (name, category, photo, election_id) VALUES (?,?,?,?)",
            (name, category, photo_path, election_id))
    flash("Candidate added to election.", "ok")
    return redirect(url_for("admin"))

@app.route("/schedule_election", methods=["POST"])
@login_required(role="admin")
def schedule_election():
    title = request.form.get("title","").strip()
    year = request.form.get("year","").strip()
    category = request.form.get("category","").strip()
    from datetime import timedelta
    tz_offset = int(request.form.get("tz_offset", "0"))
    start_raw = (request.form.get("start_time") or "").strip()
    end_raw   = (request.form.get("end_time") or "").strip()
    def to_utc_iso(local_str):
        if not local_str:
            return ""
        if len(local_str) == 16:
            local_str = local_str + ":00"
        dt = datetime.fromisoformat(local_str)
        utc_dt = dt - timedelta(minutes=tz_offset)
        return utc_dt.replace(tzinfo=timezone.utc).isoformat()
    start_time = to_utc_iso(start_raw)
    end_time   = to_utc_iso(end_raw)
    cand_limit = request.form.get("candidate_limit","").strip()

    if not title or not year or not category or not start_time or not end_time:
        flash("All fields are required for scheduling.", "error")
        return redirect(url_for("admin"))

    sdt = parse_iso(start_time); edt = parse_iso(end_time)
    if not sdt or not edt or edt <= sdt:
        flash("Invalid time window. End must be after start.", "error")
        return redirect(url_for("admin"))

    try:
        cand_limit_val = int(cand_limit) if cand_limit else None
        if cand_limit_val is not None and cand_limit_val < 1:
            raise ValueError
    except ValueError:
        flash("Candidate limit must be a positive number.", "error")
        return redirect(url_for("admin"))

    created_by = session.get("user_id")
    execute(
        "INSERT INTO elections (title, year, category, start_time, end_time, created_by, candidate_limit) VALUES (?,?,?,?,?,?,?)",
        (title, int(year), category, start_time, end_time, created_by, cand_limit_val)
    )
    flash("Election scheduled.", "ok")
    return redirect(url_for("admin"))

# ----------- Voting & Results -----------
def current_active_election():
    rows = query("SELECT * FROM elections ORDER BY start_time DESC")
    now = now_utc()
    for e in rows:
        s = parse_iso(e["start_time"]); t = parse_iso(e["end_time"])
        if s and t and s <= now <= t:
            return e
    return None

@app.route("/voter")
@login_required(role="voter")
def voter_panel():
    e = current_active_election()
    if not e:
        return render_template("voter.html", election=None, voted=False, candidates=[])

    voted = bool(query("SELECT 1 FROM votes WHERE voter_id=? AND election_id=?", (session["user_id"], e["id"]), one=True))
    candidates = query("SELECT * FROM candidates WHERE election_id=?", (e["id"],))
    return render_template("voter.html", election=e, voted=voted, candidates=candidates)

@app.route("/vote", methods=["POST"])
@login_required(role="voter")
def vote():
    try:
        election_id = int(request.form.get("election_id", "0"))
        candidate_id = int(request.form.get("candidate_id", "0"))
    except ValueError:
        flash("Invalid vote submission.", "error")
        return redirect(url_for("voter_panel"))

    e = query("SELECT * FROM elections WHERE id=?", (election_id,), one=True)
    if not e:
        flash("No election is scheduled right now.", "warn")
        return redirect(url_for("voter_panel"))

    now = now_utc()
    s = parse_iso(e["start_time"]); t = parse_iso(e["end_time"])
    if not s or not t or not (s <= now <= t):
        flash("This election is not active.", "warn")
        return redirect(url_for("voter_panel"))

    if query("SELECT 1 FROM votes WHERE voter_id=? AND election_id=?", (session["user_id"], election_id), one=True):
        flash("You have already voted in this election.", "warn")
        return redirect(url_for("voter_panel"))

    c = query("SELECT * FROM candidates WHERE id=? AND election_id=?", (candidate_id, election_id), one=True)
    if not c:
        flash("Invalid candidate selection.", "error")
        return redirect(url_for("voter_panel"))

    execute(
        "INSERT INTO votes (voter_id, candidate_id, election_id, timestamp) VALUES (?,?,?,?)",
        (session["user_id"], candidate_id, election_id, now.isoformat())
    )
    flash("Vote recorded. Thank you!", "ok")
    return redirect(url_for("voter_panel"))

@app.route("/results")
@login_required(role="admin")
def results():
    election_id = request.args.get("election_id")
    if election_id:
        e = query("SELECT * FROM elections WHERE id=?", (election_id,), one=True)
    else:
        e = current_active_election()
    if not e:
        flash("No election selected/active.", "warn")
        return redirect(url_for("admin"))

    rows = query("""
        SELECT c.name, COUNT(v.id) as votes
        FROM candidates c
        LEFT JOIN votes v ON v.candidate_id=c.id AND v.election_id=?
        WHERE c.election_id=?
        GROUP BY c.id
        ORDER BY votes DESC, c.name ASC
    """, (e["id"], e["id"]))

    results = [{"name": r["name"], "votes": r["votes"]} for r in rows]
    return render_template("result.html", election=e, results=results, elections=query("SELECT * FROM elections ORDER BY start_time DESC"))

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=False)
