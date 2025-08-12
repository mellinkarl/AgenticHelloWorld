from __future__ import annotations
import contextvars

_request_id: contextvars.ContextVar[str | None] = contextvars.ContextVar("request_id", default=None)

def set_request_id(value: str | None) -> None:
    _request_id.set(value)

def get_request_id() -> str | None:
    return _request_id.get()
