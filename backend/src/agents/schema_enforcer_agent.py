from __future__ import annotations
from typing import Mapping, Dict, Any, Optional, Type
import json

from pydantic import BaseModel as PydBaseModel # v2 ok for typing only

class SchemaEnforcerAgent:
    """
    Ensure output is valid as text or JSON. If mode='json' and parsing fails,
    optionally wraps into {"text": "..."} or tries a simple repair.
    Output: {"text": "..."} or {"json": {...}} (pick one, configurable).
    """
    def __init__(self, *, mode: str = "text", prefer_key: str = "text",
                 schema: Optional[Type[PydBaseModel]] = None, wrap_key: str = "text"):
        assert mode in ("text", "json")
        self.mode = mode
        self.prefer_key = prefer_key
        self.schema = schema
        self.wrap_key = wrap_key

    def invoke(self, state: Mapping[str, Any]) -> Dict[str, Any]:
        if self.mode == "text":
            text = str(state.get(self.prefer_key) or state.get("text") or state.get("draft") or "")
            return {"text": text}
        # json mode
        source = str(state.get(self.prefer_key) or state.get("text") or state.get("draft") or "")
        try:
            obj = json.loads(source)
            if self.schema is not None:
                obj = self.schema.model_validate(obj).model_dump()
            return {"json": obj}
        except Exception:
            # wrap as text if can't parse json
            return {"text": source}
