from __future__ import annotations
from typing import Mapping, Dict, Any, Optional

from ..config import get_logger
from ..core.instrumentation import log_invoke_start, log_invoke_end

log = get_logger(__name__)

class DiffEnforcerAgent:
    """
    Ensures that the rewritten text differs from the original draft.

    If the text is identical to the draft, it can:
      1. Replace it entirely with the value from another state key (`use_suffix_key`),
         if that key exists.
      2. Append the value from `use_suffix_key` in parentheses (if replace_with_key=False).
      3. Append a fallback suffix string (`fallback_suffix`) if no suffix key is available.

    This helps guarantee that downstream steps don't get identical text
    when a change is expected.
    """

    def __init__(
        self,
        *,
        text_key: str = "text",                # Key for the rewritten text in state
        draft_key: str = "draft",              # Key for the original draft in state
        use_suffix_key: Optional[str] = None,  # State key whose value will be used as suffix or replacement
        fallback_suffix: str = " (modified)",  # Suffix to append if no suffix key is available
        replace_with_key: bool = True,         # Whether to replace text entirely with suffix key value
    ):
        self.text_key = text_key
        self.draft_key = draft_key
        self.use_suffix_key = use_suffix_key
        self.fallback_suffix = fallback_suffix
        self.replace_with_key = replace_with_key

    def invoke(self, state: Mapping[str, Any]) -> Dict[str, Any]:
        """
        Apply the difference-enforcement logic synchronously.

        Steps:
          - Get the original draft and rewritten text.
          - If they are identical:
              * Use `use_suffix_key` (replace or append), OR
              * Use `fallback_suffix` if no suffix key is provided.
        """
        t0 = log_invoke_start(log, "DiffEnforcerAgent", state)

        # Extract and normalize
        draft = str(state.get(self.draft_key, "")).strip()
        text = str(state.get(self.text_key, "")).strip()

        # If no change has been made, enforce difference
        if text == draft:
            if self.use_suffix_key and state.get(self.use_suffix_key):
                if self.replace_with_key:
                    # Replace text entirely with the suffix key's value
                    text = str(state[self.use_suffix_key])
                else:
                    # Append suffix key's value in parentheses
                    text = text + f" ({state[self.use_suffix_key]})"
            elif self.fallback_suffix:
                # Append a static fallback suffix
                text = text + self.fallback_suffix

        out = {self.text_key: text}
        log_invoke_end(log, "DiffEnforcerAgent", t0, out)
        return out

    async def ainvoke(self, state: Mapping[str, Any]) -> Dict[str, Any]:
        """
        Async-compatible API.
        Currently just calls the sync version since this is CPU-only logic.
        """
        return self.invoke(state)
