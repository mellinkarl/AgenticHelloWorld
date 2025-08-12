from __future__ import annotations
from typing import Mapping, Dict, Any, List, Optional
import json
import re

from ..config import get_logger
from ..core.instrumentation import log_invoke_start, log_invoke_end

log = get_logger(__name__)

class RuleRouterAgent:
    """
    A deterministic, rule-based router that evaluates text against predefined
    constraints and decides whether it should PASS or be sent for REFINE.

    Output State:
        {
            "route": "PASS" | "REFINE",
            "reasons": [str, ...]  # Explanation for failure (empty if passed)
        }

    Supported rules (evaluated in order, stop at first failure):
        - min_len: Fail if text is shorter than this length.
        - max_len: Fail if text is longer than this length.
        - must_include: Fail if any required substrings are missing.
        - forbid: Fail if any forbidden substrings are present.
        - require_json: Fail if the text is not valid JSON.
        - regex: Fail if it does not match the given regex pattern.
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
        # Rule configuration
        self.min_len = min_len
        self.max_len = max_len
        self.must_include = must_include or []
        self.forbid = forbid or []
        self.require_json = require_json
        self.regex = re.compile(regex) if regex else None

        # Routing labels
        self.pass_route = pass_route
        self.fail_route = fail_route

    def invoke(self, state: Mapping[str, Any]) -> Dict[str, Any]:
        """
        Evaluate the input `draft` text against the rules.

        Args:
            state: Mapping that should contain "draft" as the text to check.

        Returns:
            dict: {
                "route": "PASS" | "REFINE",
                "reasons": [str, ...]
            }
        """
        # Log start of processing
        t0 = log_invoke_start(log, "RuleRouterAgent", state)

        text = str(state.get("draft", ""))
        reasons: List[str] = []
        route = self.pass_route  # Default to pass

        # 1. Minimum length check
        if self.min_len is not None and len(text) < self.min_len:
            route, reasons = self.fail_route, [f"min_len<{self.min_len}"]

        # 2. Maximum length check
        elif self.max_len is not None and len(text) > self.max_len:
            route, reasons = self.fail_route, [f"max_len>{self.max_len}"]

        # 3. Must-include keywords check
        elif self.must_include and not all(k.lower() in text.lower() for k in self.must_include):
            missing = [k for k in self.must_include if k.lower() not in text.lower()]
            route, reasons = self.fail_route, [f"missing:{','.join(missing)}"]

        # 4. Forbidden keywords check
        elif self.forbid and any(k.lower() in text.lower() for k in self.forbid):
            bad = [k for k in self.forbid if k.lower() in text.lower()]
            route, reasons = self.fail_route, [f"forbidden:{','.join(bad)}"]

        # 5. JSON validity check
        elif self.require_json:
            try:
                json.loads(text)
            except Exception as e:
                route, reasons = self.fail_route, [f"json_error:{type(e).__name__}"]

        # 6. Regex match check
        elif self.regex and not self.regex.search(text):
            route, reasons = self.fail_route, ["regex:no-match"]

        # Build output with route and reasons
        out = {"route": route, "reasons": reasons}

        # Log completion of processing
        log_invoke_end(log, "RuleRouterAgent", t0, out)
        return out

    async def ainvoke(self, state: Mapping[str, Any]) -> Dict[str, Any]:
        """
        Async-compatible API.
        Since checks are CPU-bound and fast, it reuses the sync logic.
        """
        return self.invoke(state)
