from __future__ import annotations
from typing import Mapping, Dict, Any, List, Optional
import re

class LengthKeywordGuardAgent:
    """
    Objective checks; returns ok + violations (composite decides next).
    """
    def __init__(
        self,
        *,
        min_len: Optional[int] = None,
        max_len: Optional[int] = None,
        must_include: Optional[List[str]] = None,
        forbid: Optional[List[str]] = None,
        regex: Optional[str] = None,
        source_key: str = "text",
    ):
        self.min_len = min_len
        self.max_len = max_len
        self.must_include = must_include or []
        self.forbid = forbid or []
        self.regex = re.compile(regex) if regex else None
        self.source_key = source_key

    def invoke(self, state: Mapping[str, Any]) -> Dict[str, Any]:
        txt = str(state.get(self.source_key, ""))
        violations: List[str] = []

        if self.min_len is not None and len(txt) < self.min_len:
            violations.append(f"min_len:{self.min_len}")
        if self.max_len is not None and len(txt) > self.max_len:
            violations.append(f"max_len:{self.max_len}")
        if self.must_include:
            for k in self.must_include:
                if k.lower() not in txt.lower():
                    violations.append(f"missing:{k}")
        if self.forbid:
            for k in self.forbid:
                if k.lower() in txt.lower():
                    violations.append(f"forbidden:{k}")
        if self.regex and not self.regex.search(txt):
            violations.append("regex:fail")

        return {"ok": len(violations) == 0, "violations": violations}
