from __future__ import annotations
from typing import Mapping, Dict, Any, List, Optional
import json
import re

class RuleRouterAgent:
    """
    Rule-based router (no tokens).
    Configurable checks: min_len, max_len, must_include, forbid, require_json, regex
    Output: {"route": "PASS" | "REFINE"}
    """
    def __init__(
        self,
        *,
        min_len: Optional[int] = None,
        max_len: Optional[int] = None,
        must_include: Optional[List[str]] = None,
        forbid: Optional[List[str]] = None,
        require_json: bool = False,
        regex: Optional[str] = None,
        pass_route: str = "PASS",
        fail_route: str = "REFINE",
    ):
        self.min_len = min_len
        self.max_len = max_len
        self.must_include = must_include or []
        self.forbid = forbid or []
        self.require_json = require_json
        self.regex = re.compile(regex) if regex else None
        self.pass_route = pass_route
        self.fail_route = fail_route

    def invoke(self, state: Mapping[str, Any]) -> Dict[str, Any]:
        text = str(state.get("draft", ""))

        if self.min_len is not None and len(text) < self.min_len:
            return {"route": self.fail_route}
        if self.max_len is not None and len(text) > self.max_len:
            return {"route": self.fail_route}
        if self.must_include and not all(k.lower() in text.lower() for k in self.must_include):
            return {"route": self.fail_route}
        if self.forbid and any(k.lower() in text.lower() for k in self.forbid):
            return {"route": self.fail_route}
        if self.require_json:
            try:
                json.loads(text)
            except Exception:
                return {"route": self.fail_route}
        if self.regex and not self.regex.search(text):
            return {"route": self.fail_route}
        return {"route": self.pass_route}
