Render deployment quick guide

This file contains the minimal steps to deploy this Flask app (`app.py`) to Render using GitHub.

Prerequisites
- Git installed and repo pushed to GitHub
- A Render account
- (Optional) Postgres provisioned on Render if you want persistent DB

1) Commit & push
PowerShell (run inside project root):

```powershell
git init  # if not already a repo
git add .
git commit -m "Final project ready for Render"
# create a GitHub repo and replace <your-repo-url> below
git remote add origin <your-repo-url>
git branch -M main
git push -u origin main
```

2) Create Render web service
- In Render dashboard: New -> Web Service -> Connect repo -> select this repo
- Environment: Python
- Start command: (Procfile is present; Render will use it) or set explicitly:
  gunicorn app:app --bind 0.0.0.0:$PORT --workers=2 --threads=4 --timeout 120
- Set Python version to 3.12 (optional)

3) Environment variables (Render dashboard -> Environment)
- SECRET_KEY: set to a secure random string (REQUIRED)
- (Optional) DATABASE_URL: postgres://user:pass@host:port/dbname — set if you want Postgres
  - If using Postgres, set RUN_MIGRATE=true to run migrations at startup
- (Optional, for email) SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS, SMTP_FROM
- (Optional) TZ=Asia/Kolkata

4) Files & storage
- Note: file uploads go to `static/uploads` (local). Render's filesystem is ephemeral — use S3 or similar for persistent storage in production.

5) Quick local verification (before pushing)
PowerShell commands:

```powershell
# syntax check
python -m py_compile .\app.py
python -m py_compile .\scripts\init_sqlite_db.py
python -m py_compile .\db_pg.py

# run smoke test (uses local SQLite)
$env:PYTHONPATH='.'; python .\scripts\smoke_test.py
```

6) Post-deploy checks on Render
- Visit your service URL -> should return the app homepage
- Login with admin credentials seeded locally (if using local SQLite seed) or create admin user
- If using Postgres and RUN_MIGRATE, check Render logs for migration success

7) Troubleshooting
- If app errors on startup: check Render logs (Deploy -> View logs)
- If DB errors: ensure `DATABASE_URL` is correct and RUN_MIGRATE set if required
- If emails not sent: ensure SMTP env vars are set

That's it — this repo is ready for Render deployment. Good luck with your submission!

8) Optional: Test Postgres migrations locally with Docker
 - A docker-compose is included (`docker-compose.yml`) which runs Postgres on localhost:5432.
 - Steps (PowerShell):

```powershell
# start Postgres
docker-compose up -d

# set the DATABASE_URL to the local container
$env:DATABASE_URL='postgres://vsuser:vsPass@localhost:5432/vsdb'

# run migrations (this will call db_pg.migrate_and_seed())
python .\scripts\test_postgres_migrate.py

# after test, stop containers
docker-compose down
```

If migrations complete successfully, you can set your Render `DATABASE_URL` to the managed Postgres DB and set `RUN_MIGRATE=true` to run automatically at deploy.