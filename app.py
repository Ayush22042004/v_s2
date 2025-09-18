
import os
import sqlite3
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
IST = ZoneInfo('Asia/Kolkata')
from functools import wraps

from flask import Flask, render_template, request, redirect, url_for, flash, session
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
    db.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_votes_unique ON votes(voter_id, election_id)")
    db.commit()

def seed_admin():
    admin = query("SELECT id FROM users WHERE role='admin' LIMIT 1", one=True)
    if not admin:
        execute("INSERT INTO users (name,email,username,password,role) VALUES (?,?,?,?,?)",
                ("Admin","admin@example.com","admin", generate_password_hash("admin123"), "admin"))

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
        dt = datetime.fromisoformat((s or "").replace("Z", ""))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def to_ist(dt):
    try:
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(IST)
    except Exception:
        return dt

def now_utc():
    return datetime.now(timezone.utc)

# -------------- Routes --------------
@app.route("/")
def index():
    user = query("SELECT * FROM users WHERE id=?", (session["user_id"],), one=True) if "user_id" in session else None
    active = query("SELECT * FROM elections ORDER BY start_time DESC LIMIT 5")
    return render_template("index.html", user=user, elections=active)

@app.route("/signup", methods=["GET","POST"])
def signup():
    if request.method == "POST":
        name = request.form.get("name","").strip()
        email = (request.form.get("email","").strip() or None)
        username = request.form.get("username","").strip().lower()
        password = request.form.get("password","")
        id_number = request.form.get("id_number","").strip()
        if not name or not username or not password or not id_number:
            flash("All fields except email are required.", "error"); return redirect(url_for("signup"))
        if query("SELECT 1 FROM users WHERE lower(username)=?", (username,), one=True):
            flash("Username already taken.", "error"); return redirect(url_for("signup"))
        if email and query("SELECT 1 FROM users WHERE lower(email)=?", (email.lower(),), one=True):
            flash("Email already registered.", "error"); return redirect(url_for("signup"))
        execute("INSERT INTO users (name,email,username,password,role,id_number) VALUES (?,?,?,?,?,?)",
                (name, email.lower() if email else None, username, generate_password_hash(password), "voter", id_number))
        flash("Account created. Please login.", "ok"); return redirect(url_for("login"))
    return render_template("signup.html")

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username","").strip().lower()
        password = request.form.get("password","")
        user = query("SELECT * FROM users WHERE lower(username)=?", (username,), one=True)
        if user and check_password_hash(user["password"], password):
            session["user_id"] = user["id"]; session["role"]=user["role"]
            flash("Welcome back!", "ok"); return redirect(url_for("index"))
        flash("Invalid credentials.", "error")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear(); flash("Logged out.", "ok"); return redirect(url_for("index"))

# ----------- Admin Dashboard -----------
@app.route("/admin")
@login_required(role="admin")
def admin():
    rows = query("SELECT * FROM elections ORDER BY start_time DESC")
    ongoing, scheduled, ended = classify_elections(rows)
    return render_template("admin.html", ongoing=ongoing, scheduled=scheduled, ended=ended, elections=rows)
@app.route("/add_candidate", methods=["POST"])
@login_required(role="admin")
def add_candidate():
    name = request.form.get("name","").strip()
    category = request.form.get("category","").strip() or "General"
    election_id = request.form.get("election_id","").strip()
    if not name or not election_id:
        flash("Candidate name and election are required.", "error"); return redirect(url_for("admin"))
    try:
        election_id = int(election_id)
    except ValueError:
        flash("Invalid election selected.", "error"); return redirect(url_for("admin"))
    e = query("SELECT id, candidate_limit, created_by FROM elections WHERE id=?", (election_id,), one=True)
    if not e: flash("Selected election does not exist.", "error"); return redirect(url_for("admin"))
    if e["created_by"] and e["created_by"] != session.get("user_id"):
        flash("You can only add candidates to your own elections.", "error"); return redirect(url_for("admin"))
    if e["candidate_limit"] is not None:
        cnt = query("SELECT COUNT(*) AS c FROM candidates WHERE election_id=?", (election_id,), one=True)["c"]
        if cnt >= e["candidate_limit"]:
            flash("Candidate limit reached for this election.", "warn"); return redirect(url_for("admin"))
    photo_path=None; f=request.files.get("photo")
    if f and f.filename:
        filename = secure_filename(f.filename)
        uploads_dir = os.path.join(APP_DIR, "static", "uploads"); os.makedirs(uploads_dir, exist_ok=True)
        f.save(os.path.join(uploads_dir, filename)); photo_path=f"uploads/{filename}"
    execute("INSERT INTO candidates (name,category,photo,election_id) VALUES (?,?,?,?)",
            (name, category, photo_path, election_id))
    flash("Candidate added to election.", "ok"); return redirect(url_for("admin"))

@app.route("/schedule_election", methods=["POST"])
@login_required(role="admin")
def schedule_election():
    title = request.form.get("title","").strip()
    year = request.form.get("year","").strip()
    category = request.form.get("category","").strip()
    tz_offset = int(request.form.get("tz_offset","0"))  # minutes from UTC to local (JS getTimezoneOffset)
    start_raw = (request.form.get("start_time") or "").strip()
    end_raw   = (request.form.get("end_time") or "").strip()
    start_time_utc = (request.form.get('start_time_utc') or '').strip()
    end_time_utc   = (request.form.get('end_time_utc') or '').strip()
    if not title or not year or not category or not start_raw or not end_raw:
        flash("All fields are required for scheduling.", "error"); return redirect(url_for("admin"))
    def to_utc_iso(local_str):
        if len(local_str)==16: local_str += ":00"
        dt = datetime.fromisoformat(local_str)  # naive local wall time
        # JS getTimezoneOffset() is minutes DIFFERENCE from UTC to local (UTC - local)
        # Correct conversion: UTC = local + offset_minutes
        utc_dt = dt - timedelta(minutes=tz_offset)
        return utc_dt.replace(tzinfo=timezone.utc).isoformat()
    start_time = to_utc_iso(start_raw); end_time = to_utc_iso(end_raw)
    sdt = parse_iso(start_time); edt = parse_iso(end_time)
    if not sdt or not edt or edt <= sdt:
        flash("Invalid time window. End must be after start.", "error"); return redirect(url_for("admin"))
    created_by = session.get("user_id")
    cand_limit = request.form.get("candidate_limit","").strip()
    try:
        cand_limit_val = int(cand_limit) if cand_limit else None
        if cand_limit_val is not None and cand_limit_val < 1: raise ValueError
    except ValueError:
        flash("Candidate limit must be a positive number.", "error"); return redirect(url_for("admin"))
    execute("INSERT INTO elections (title,year,category,start_time,end_time,created_by,candidate_limit) VALUES (?,?,?,?,?,?,?)",
            (title, int(year), category, start_time, end_time, created_by, cand_limit_val))
    flash("Election scheduled.", "ok"); return redirect(url_for("admin"))

# ----------- Voting & Results -----------
def current_active_election():
    rows = query("SELECT * FROM elections ORDER BY start_time DESC")
    now = now_utc()
    for e in rows:
        s = parse_iso(e["start_time"]); t = parse_iso(e["end_time"])
        if s and t and s <= now <= t:
            return e
    return None


def to_ist(dt):
    try:
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(IST)
    except Exception:
        return dt

voted = bool(query("SELECT 1 FROM votes WHERE voter_id=? AND election_id=?", (session["user_id"], e["id"]), one=True))
    candidates = query("SELECT * FROM candidates WHERE election_id=?", (e["id"],))
    return render_template("voter.html", election=e, voted=voted, candidates=candidates)

@app.route("/vote", methods=["POST"])
@login_required(role="voter")
def vote():
    try:
        election_id = int(request.form.get("election_id","0"))
        candidate_id = int(request.form.get("candidate_id","0"))
    except ValueError:
        flash("Invalid vote submission.", "error"); return redirect(url_for("voter_panel"))
    e = query("SELECT * FROM elections WHERE id=?", (election_id,), one=True)
    if not e: flash("No election is scheduled right now.", "warn"); return redirect(url_for("voter_panel"))
    now = now_utc(); s = parse_iso(e["start_time"]); t = parse_iso(e["end_time"])
    if not s or not t or not (s <= now <= t):
        flash("This election is not active.", "warn"); return redirect(url_for("voter_panel"))
    if query("SELECT 1 FROM votes WHERE voter_id=? AND election_id=?", (session["user_id"], election_id), one=True):
        flash("You have already voted in this election.", "warn"); return redirect(url_for("voter_panel"))
    c = query("SELECT * FROM candidates WHERE id=? AND election_id=?", (candidate_id, election_id), one=True)
    if not c: flash("Invalid candidate selection.", "error"); return redirect(url_for("voter_panel"))
    execute("INSERT INTO votes (voter_id,candidate_id,election_id,timestamp) VALUES (?,?,?,?)",
            (session["user_id"], candidate_id, election_id, now.isoformat()))
    flash("Vote recorded. Thank you!", "ok"); return redirect(url_for("voter_panel"))

@app.route("/results")
@login_required(role="admin")
def results():
    election_id = request.args.get("election_id")
    e = query("SELECT * FROM elections WHERE id=?", (election_id,), one=True) if election_id else current_active_election()
    if not e: flash("No election selected/active.", "warn"); return redirect(url_for("admin"))
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


@app.template_filter("istfmt")
def istfmt(value):
    try:
        dt = parse_iso(value)
        dt = to_ist(dt)
        return dt.strftime("%d %b %Y, %I:%M %p IST")
    except Exception:
        return value


def classify_elections(rows):
    now = now_utc()
    ongoing, scheduled, ended = [], [], []
    for e in rows:
        s = parse_iso(e["start_time"]); t = parse_iso(e["end_time"])
        if s and t:
            if s <= now <= t: ongoing.append(e)
            elif now < s: scheduled.append(e)
            else: ended.append(e)
    return ongoing, scheduled, ended


@app.route("/results_excel/<int:eid>")
@login_required()
def results_excel(eid):
    import io
    from openpyxl import Workbook
    e = query("SELECT * FROM elections WHERE id=?", (eid,), one=True)
    if not e:
        flash("Election not found", "error"); return redirect(url_for("admin"))
    rows = query("""
        SELECT c.name, COUNT(v.id) as votes
        FROM candidates c
        LEFT JOIN votes v ON v.candidate_id=c.id AND v.election_id=?
        WHERE c.election_id=?
        GROUP BY c.id
        ORDER BY votes DESC, c.name ASC
    """, (eid, eid))
    wb = Workbook()
    ws = wb.active; ws.title = "Results"
    ws.append(["Election", e["title"] or e["category"]])
    ws.append(["Start", e["start_time"], "End", e["end_time"]])
    ws.append([]); ws.append(["Candidate", "Votes"])
    for r in rows: ws.append([r["name"], r["votes"]])
    stream = io.BytesIO(); wb.save(stream); stream.seek(0)
    return (stream.read(), 200, {
        "Content-Type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "Content-Disposition": f"attachment; filename=results_{eid}.xlsx",
    })


@app.route("/voter")
@login_required(role="voter")
def voter_panel():
    rows = query("SELECT * FROM elections ORDER BY start_time ASC")
    ongoing, scheduled, ended = classify_elections(rows)

    cand_map = {}
    for e in ongoing:
        cand_map[e["id"]] = query(
            "SELECT * FROM candidates WHERE election_id=?", (e["id"],)
        )

    return render_template(
        "voter.html",
        ongoing=ongoing,
        scheduled=scheduled,
        ended=ended,
        cand_map=cand_map,
    )
