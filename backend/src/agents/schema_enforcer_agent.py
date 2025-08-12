from __future__ import annotations
from typing import Mapping, Dict, Any, Optional, Type
import json

from ..config import get_logger
from ..core.instrumentation import log_invoke_start, log_invoke_end
from pydantic import BaseModel as PydBaseModel  

log = get_logger(__name__)


class SchemaEnforcerAgent:
    """
    Normalizes the agent output into either plain text or JSON.

    Supported modes:
      - mode="text":
          Selects a text-like field from the state (in priority order: prefer_key → "text" → "draft")
          and returns it as {"text": "..."}.

      - mode="json":
          Attempts to parse the chosen field as JSON (via json.loads).
          If a Pydantic schema is provided, validates the parsed object
          and coerces it into a Python dict.  
          If parsing or validation fails, falls back to {"text": raw_string}.

    Parameters:
      mode       : "text" or "json"
      prefer_key : First choice field to extract from state
      schema     : Optional Pydantic model class (used only if mode="json")
      wrap_key   : Reserved for compatibility; unused in this minimal implementation
    """

    def __init__(
        self,
        *,
        mode: str = "text",
        prefer_key: str = "text",
        schema: Optional[Type["PydBaseModel"]] = None,  # type hint only
        wrap_key: str = "text",
    ):
        """
        Initialize the SchemaEnforcerAgent.

        :param mode: Processing mode, either "text" or "json".
        :param prefer_key: Primary key to pull data from the state.
        :param schema: Optional Pydantic model class (used only in json mode).
        :param wrap_key: Currently unused; kept for API compatibility.
        """
        assert mode in ("text", "json"), "mode must be either 'text' or 'json'"
        self.mode = mode
        self.prefer_key = prefer_key
        self.schema = schema
        self.wrap_key = wrap_key

    def invoke(self, state: Mapping[str, Any]) -> Dict[str, Any]:
        """
        Normalize the state into a standard structure.

        Workflow:
          1. Log the start event (includes state previews and metadata).
          2. In text mode:
               - Pick the first available field: prefer_key → "text" → "draft"
               - Return {"text": <string>}
          3. In json mode:
               - Extract the same way as above
               - Try json.loads to parse it
               - If schema is provided, validate/normalize via Pydantic
               - On any failure, fall back to {"text": raw}
          4. Log the end event with output previews.
          5. Return the normalized output dict.
        """
        t0 = log_invoke_start(log, "SchemaEnforcerAgent", state)

        # TEXT MODE
        if self.mode == "text":
            text = str(
                state.get(self.prefer_key)
                or state.get("text")
                or state.get("draft")
                or ""
            )
            out = {"text": text}
            log_invoke_end(log, "SchemaEnforcerAgent", t0, out)
            return out

        # JSON MODE
        raw = (
            state.get(self.prefer_key)
            or state.get("text")
            or state.get("draft")
            or ""
        )
        source = str(raw)

        try:
            obj = json.loads(source)  # Attempt to parse JSON

            # If schema is set, validate with Pydantic v2
            if self.schema is not None:
                from pydantic import BaseModel as PydBaseModel  # v2 ok for typing & runtime
                if not issubclass(self.schema, PydBaseModel):
                    raise TypeError("schema must be a subclass of Pydantic BaseModel")
                obj = self.schema.model_validate(obj).model_dump()

            out: Dict[str, Any] = {"json": obj}

        except Exception:
            # Parsing or validation failed → return as plain text
            out = {"text": source}

        log_invoke_end(log, "SchemaEnforcerAgent", t0, out)
        return out

    async def ainvoke(self, state: Mapping[str, Any]) -> Dict[str, Any]:
        """
        Async-compatible entrypoint.
        This logic is synchronous and CPU-bound, so we reuse the sync path.
        """
        return self.invoke(state)
