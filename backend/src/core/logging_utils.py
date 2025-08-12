from __future__ import annotations

def clip_text(s: str, limit: int = 120) -> str:
    """Compact text for logs."""
    s = (s or "").replace("\n", " ").strip()
    return s if len(s) <= limit else s[:limit] + "…"
