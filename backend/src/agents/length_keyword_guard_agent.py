from __future__ import annotations
from typing import Mapping, Dict, Any, List, Optional
import re

from ..config import get_logger
from ..core.instrumentation import log_invoke_start, log_invoke_end

log = get_logger(__name__)

class LengthKeywordGuardAgent:
    """
    Performs objective text checks and returns:
        {
            "ok": bool,            # True if no violations
            "violations": [str]    # List of failed rules
        }

    Configuration options:
        - min_len / max_len: Text length boundaries.
        - must_include: List of substrings that must appear (case-insensitive).
        - forbid: List of substrings that must NOT appear (case-insensitive).
        - regex: Pattern that must match at least once.
        - source_key: Which state field to check (default is "text").

    This agent does not decide routing itself — it only reports results
    so that a composite agent or pipeline can decide what to do next.
    """

    def __init__(
        self,
        *,
        min_len: Optional[int] = None,               # Minimum length allowed
        max_len: Optional[int] = None,               # Maximum length allowed
        must_include: Optional[List[str]] = None,    # Substrings that must appear
        forbid: Optional[List[str]] = None,          # Substrings that must NOT appear
        regex: Optional[str] = None,                 # Must match this pattern
        source_key: str = "text",                    # Which state key to check
    ):
        self.min_len = min_len
        self.max_len = max_len
        self.must_include = must_include or []
        self.forbid = forbid or []
        self.regex = re.compile(regex) if regex else None
        self.source_key = source_key

    def invoke(self, state: Mapping[str, Any]) -> Dict[str, Any]:
        """
        Perform all configured checks on the text from `source_key`.

        Returns:
            {
                "ok": True if no violations found, False otherwise,
                "violations": list of strings describing each violation
            }
        """
        t0 = log_invoke_start(log, "LengthKeywordGuardAgent", state)

        # Get the text to check
        txt = str(state.get(self.source_key, ""))

        violations: List[str] = []

        # Length checks
        if self.min_len is not None and len(txt) < self.min_len:
            violations.append(f"min_len:{self.min_len}")
        if self.max_len is not None and len(txt) > self.max_len:
            violations.append(f"max_len:{self.max_len}")

        # Required keywords
        for k in self.must_include:
            if k.lower() not in txt.lower():
                violations.append(f"missing:{k}")

        # Forbidden keywords
        for k in self.forbid:
            if k.lower() in txt.lower():
                violations.append(f"forbidden:{k}")

        # Regex match
        if self.regex and not self.regex.search(txt):
            violations.append("regex:fail")

        out = {
            "ok": len(violations) == 0,   # True if no violations
            "violations": violations
        }

        log_invoke_end(log, "LengthKeywordGuardAgent", t0, out)
        return out

    async def ainvoke(self, state: Mapping[str, Any]) -> Dict[str, Any]:
        """
        Async-compatible API.
        Currently just runs the synchronous validation since this is CPU-bound.
        """
        return self.invoke(state)
