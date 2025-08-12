from __future__ import annotations
from typing import Mapping, Dict, Any, Optional

class DiffEnforcerAgent:
    """
    Ensure rewritten text differs from draft.
    If equal, append a suffix or use a state key as suffix (e.g., a tool result).
    """
    def __init__(self, *, text_key: str = "text", draft_key: str = "draft",
                 use_suffix_key: Optional[str] = None, fallback_suffix: str = " (modified)"):
        self.text_key = text_key
        self.draft_key = draft_key
        self.use_suffix_key = use_suffix_key
        self.fallback_suffix = fallback_suffix

    def invoke(self, state: Mapping[str, Any]) -> Dict[str, Any]:
        draft = str(state.get(self.draft_key, "")).strip()
        text = str(state.get(self.text_key, "")).strip()
        if text == draft:
            suffix = ""
            if self.use_suffix_key and state.get(self.use_suffix_key):
                suffix = f" ({state[self.use_suffix_key]})"
            elif self.fallback_suffix:
                suffix = self.fallback_suffix
            text = text + suffix
        return {self.text_key: text}
