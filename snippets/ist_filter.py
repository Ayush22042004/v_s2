from datetime import datetime, timezone
from zoneinfo import ZoneInfo
IST = ZoneInfo("Asia/Kolkata")

@app.template_filter("istfmt")
def istfmt(value):
    if not value:
        return ""
    try:
        dt = value
        if isinstance(dt, str):
            dt = datetime.fromisoformat(dt.replace("Z",""))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(IST).strftime("%d %b %Y, %I:%M %p IST")
    except Exception:
        return value
