from __future__ import annotations
from datetime import date

def get_today_iso() -> str:
    """Return today's date in ISO format (YYYY-MM-DD)."""
    return date.today().isoformat()
