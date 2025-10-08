# Minimal Patch for Your Existing Site (keep your UI, just fixes)

This bundle contains ONLY the small changes you asked for — no layout rewrites.

## What’s inside
- `templates/results.html` → Admin-only results page (simple table).
- `snippets/ist_filter.py` → Add this to your `app.py` once (IST display filter).
- `snippets/export_excel_route.py` → Add this route to `app.py` for Excel export.
- `snippets/base_nav_admin_links.html` → Copy these links into your existing navbar (admin only).
- `static/css/mobile_patch.css` → Optional small CSS to improve phone layout (no structure changes).

## 1) Install dependencies
Add to your `requirements.txt` (or ensure present):
tzdata==2024.1
openpyxl==3.1.5

## 2) Add IST display filter (copy into your app.py once)
Open `snippets/ist_filter.py` and paste its content into your `app.py`:
- imports near the top
- the `@app.template_filter("istfmt")` after you create `app = Flask(__name__)`

## 3) Use IST filter in templates
Replace any datetime display with:
{{ '{{ e.start_time|istfmt }} → {{ e.end_time|istfmt }}' }}

## 4) Admin navbar links
Open your existing `templates/base.html` and drop the snippet from `snippets/base_nav_admin_links.html`
inside your admin-only nav area.

## 5) Results page route + template
- Add the route from `snippets/export_excel_route.py` (both `/results` and `/export.xlsx` routes) into `app.py`.
- Copy `templates/results.html` to your project’s `templates/` folder.

> The Python routes assume you have a DB helper named `query` (for SELECT).
> If yours is named differently (e.g., `db.query`), rename the calls accordingly.
> The SQL only reads data; it doesn’t modify your schema.

## 6) Optional mobile polish
Copy `static/css/mobile_patch.css` to your static folder and include it in your base.html **after** your existing CSS:
<link rel="stylesheet" href="{{ '{{ url_for(''static'', filename=''css/mobile_patch.css'') }}' }}">

## 7) Redeploy
- Commit/push and redeploy.

If you hit any errors, share the traceback and I’ll adjust the patch to match your helpers.
