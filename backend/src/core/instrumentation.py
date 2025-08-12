from __future__ import annotations
import time
import re
from typing import Mapping, Dict, Any, Iterable
from logging import Logger

from .context import get_request_id

# Regex to normalize whitespace for previews
_WS = re.compile(r"\s+")

def _preview(val: Any, max_chars: int = 120) -> str:
    """
    Convert any value to a compact preview string:
    - Collapse multiple whitespace characters into single spaces.
    - Trim leading/trailing spaces.
    - Truncate to `max_chars` characters (adding ellipsis if truncated).
    """
    s = str(val)
    s = _WS.sub(" ", s).strip()
    return (s[: max_chars - 1] + "…") if len(s) > max_chars else s

def _pick_meta(state: Mapping[str, Any], keys: Iterable[str]) -> Dict[str, Any]:
    """
    Extract selected keys from a state mapping and produce
    a metadata dict with:
      - `<key>_preview`: short string preview of the value
      - `<key>_len`: length of the value (as string)
    Only includes keys that actually exist in `state`.
    """
    out: Dict[str, Any] = {}
    for k in keys:
        if k in state:
            v = state[k]
            out[f"{k}_preview"] = _preview(v)
            out[f"{k}_len"] = len(str(v))
    return out

def log_invoke_start(
    log: Logger,
    agent: str,
    state: Mapping[str, Any],
    extra: Dict[str, Any] | None = None,
) -> float:
    """
    Log the start of an agent invocation.

    - Records the time for later duration calculation.
    - Logs input keys and previews of important text fields.
    - Attaches request_id if available (for tracing across logs).
    - Merges any additional metadata from `extra`.
    """
    t0 = time.perf_counter()
    in_keys = sorted(state.keys())  # Keep a predictable order of keys
    meta = _pick_meta(state, ("user_input", "draft", "text"))
    payload = {"agent": agent, "stage": "start", "in_keys": in_keys, **meta}
    if extra:
        payload.update(extra)

    # Attach request ID for correlation if available
    rid = get_request_id()
    if rid:
        payload["request_id"] = rid

    # Debug-level logging for start of invocation
    log.debug("agent.invoke.start", extra=payload)
    return t0

def log_invoke_end(
    log: Logger,
    agent: str,
    t0: float,
    out: Mapping[str, Any],
    extra: Dict[str, Any] | None = None,
) -> None:
    """
    Log the end of an agent invocation.

    - Calculates elapsed time in milliseconds from `t0`.
    - Logs output keys and previews of key output fields.
    - Includes special fields like 'ok' and 'violations' if present.
    - Attaches request_id for trace correlation.
    - Merges any additional metadata from `extra`.
    """
    dt = int((time.perf_counter() - t0) * 1000)
    out_keys = sorted(out.keys())
    meta = _pick_meta(out, ("text", "draft", "route"))

    payload = {
        "agent": agent,
        "stage": "end",
        "ms": dt,
        "out_keys": out_keys,
        **meta
    }

    # Include 'ok' flag if present
    if "ok" in out:
        payload["ok"] = out["ok"]

    # Include violations info if present
    if "violations" in out:
        try:
            payload["violations"] = list(out["violations"])
        except Exception:
            payload["violations_count"] = 1  # Fallback if not iterable

    if extra:
        payload.update(extra)

    # Attach request ID for correlation
    rid = get_request_id()
    if rid:
        payload["request_id"] = rid

    # Info-level logging for end of invocation
    log.info("agent.invoke.end", extra=payload)
