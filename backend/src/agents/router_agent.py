from __future__ import annotations
from typing import Dict, Any

class RouterAgent:
    """
    Agent-2: Deterministic router (locally testable).
    Rule: PASS iff draft.strip() == 'OK.' unless force_refine=True in state.
    """
    def __init__(self, require_exact: str = "OK."):
        self.require_exact = require_exact

    def invoke(self, state: Dict[str, Any]) -> Dict[str, Any]:
        if state.get("force_refine"):
            return {"route": "REFINE"}
        draft = (state.get("draft") or "").strip()
        return {"route": "PASS" if draft == self.require_exact else "REFINE"}
