from __future__ import annotations
from datetime import date, timedelta

def get_today_iso() -> str:
    return date.today().isoformat()


def get_yesterday_iso() -> str:
    return (date.today() - timedelta(days=1)).isoformat()