from __future__ import annotations
from typing import Mapping, Dict, Any, Optional

class DiffEnforcerAgent:
    """
    Ensure rewritten text differs from draft.
    If equal, append a suffix or use a state key as suffix (e.g., a tool result).
    """
    def __init__(self, *, text_key="text", draft_key="draft", use_suffix_key: Optional[str] = None, fallback_suffix: str = " (modified)", replace_with_key: bool = True):
        self.text_key = text_key
        self.draft_key = draft_key
        self.use_suffix_key = use_suffix_key
        self.fallback_suffix = fallback_suffix
        self.replace_with_key = replace_with_key

    def invoke(self, state: Mapping[str, Any]) -> Dict[str, Any]:
        draft = str(state.get(self.draft_key, "")).strip()
        text = str(state.get(self.text_key, "")).strip()
        if text == draft:
            if self.use_suffix_key and state.get(self.use_suffix_key):
                if self.replace_with_key:
                    text = str(state[self.use_suffix_key])          
                else:
                    text = text + f" ({state[self.use_suffix_key]})"  
            elif self.fallback_suffix:
                text = text + self.fallback_suffix
        return {self.text_key: text}
