from __future__ import annotations
from typing import Mapping, Dict, Any

from ..config import get_logger
from ..core.instrumentation import log_invoke_start, log_invoke_end

log = get_logger(__name__)

class TemplateFillerAgent:
    """
    Fills a Python `.format()`-style string template with values from the current state.

    Typical use:
      - Provide a template string containing placeholders, e.g.:
            "Hello {name}, today is {day}."
      - At runtime, the agent will replace `{name}` and `{day}` with corresponding
        values from the state mapping.

    Parameters:
      template    : A string with `{placeholder}` keys to be replaced.
      output_key  : The state key under which the filled string will be stored
                    in the returned output (default is `"text"`).

    Behavior:
      - Uses Python's built-in `str.format(**state)` for substitution.
      - If a placeholder's key is missing from the state, or if formatting
        raises any exception, the original template is returned unchanged
        (non-strict mode — avoids failure).
    """
    def __init__(self, template: str, *, output_key: str = "text"):
        self.template = template
        self.output_key = output_key

    def invoke(self, state: Mapping[str, Any]) -> Dict[str, Any]:
        """
        Fill the template using values from the given state.

        Steps:
          1. Log the start event with a preview of the state.
          2. Attempt to call `.format(**state)` on the template.
             - `state` is converted to a dict in case it's not a plain dict.
          3. On any exception (missing keys, type errors, bad formatting), fall
             back to returning the raw template unchanged.
          4. Store the filled (or unchanged) value under `output_key` in the
             output dict.
          5. Log the end event with a preview of the output.
          6. Return the output dict.
        """
        t0 = log_invoke_start(log, "TemplateFillerAgent", state)
        try:
            value = self.template.format(**dict(state))
        except Exception:
            value = self.template  # non-strict fallback
        out = {self.output_key: value}
        log_invoke_end(log, "TemplateFillerAgent", t0, out)
        return out

    async def ainvoke(self, state: Mapping[str, Any]) -> Dict[str, Any]:
        """
        Async-compatible version of `invoke`.

        This agent is purely CPU-bound and runs synchronously,
        so `ainvoke` simply calls `invoke`.
        """
        return self.invoke(state)
