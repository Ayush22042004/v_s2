# Render Compatibility Pack (No Code Changes)

This pack makes your existing Flask app run on Render **without changing your code**.

## What's inside
- `Procfile` — runs gunicorn on Render's `$PORT` (required).
- `requirements.txt` — infra deps only: `gunicorn`, `tzdata`, optional `openpyxl`, and (optionally) `Flask`.
- `render.yaml` — optional convenience for one-click deploy and env vars.

> Keep your current `app.py`, `templates/`, `static/`, database code, etc. as-is.

## How to use
1. **Copy these files** into your project's root (same folder as `app.py`).  
2. If you already maintain your own `requirements.txt`, just **merge** the lines from this pack (at least `gunicorn` and `tzdata`).  
3. Push the repo to GitHub.
4. On **Render** → New → **Web Service** → Connect your repo.
5. Render will detect Python. If it asks for start command, use:
   ```
   gunicorn app:app --bind 0.0.0.0:$PORT --workers=2 --threads=4 --timeout 120
   ```
6. Add env var in Render:
   - `TZ=Asia/Kolkata`  (ensures IST display if your code formats with system timezone)
7. Deploy.

### Notes
- If your app uses **SQLite**, data won't persist across deploys. That's normal for Render unless you add a Disk or switch to an external DB (e.g., Neon Postgres). This pack **does not** change your DB.
- If you don't use Excel export, remove `openpyxl` from `requirements.txt`.
- If your project already pins Flask, you can remove the Flask line here to avoid conflicts.

Happy deploying! 🚀
