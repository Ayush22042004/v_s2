# Railway Deploy Notes

## Persistence
Attach a Volume and set:
- Mount path: `/data`
- Env var: `DB_PATH=/data/voting.db`

On first deploy, the app will create the file if missing.

## Start command
Uses Procfile: `web: python app.py`

## Variables
Set `SECRET_KEY` to a random string.
