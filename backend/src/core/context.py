# Author: Harry
# Since this is just in use in logging. Do we really do this correctly??? 
"""
Module for managing context variables.

This module provides a way to store and retrieve request IDs in a thread-safe manner.

Functions:
    set_request_id(value: str | None) -> None:
        Set the request ID to the given value.

    get_request_id() -> str | None:
        Get the current request ID.

"""

from __future__ import annotations
import contextlib
import contextvars

_request_id: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "request_id",
    default=None
)

@contextlib.contextmanager
def request_id_context(rid: str | None = None):
    """
    Context manager for using a specific request ID.

    Args:
        rid (str | None, optional): The request ID to use. Defaults to None.

    Yields:
        None
    """
    old_rid = _request_id.get()
    _request_id.set(rid)
    try:
        yield
    finally:
        _request_id.set(old_rid)

def set_request_id(value: str | None) -> None:
    """
    Set the request ID to the given value.

    Args:
        value (str | None): The new request ID.

    Returns:
        None
    """
    _request_id.set(value)

def get_request_id() -> str | None:
    """
    Get the current request ID.

    Returns:
        str | None: The current request ID, or None if not set.
    """
    return _request_id.get()

