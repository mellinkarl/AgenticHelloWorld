from __future__ import annotations
from typing import Mapping, Dict, Any

class TemplateFillerAgent:
    """
    Fill a Python .format template from state safely.
    """
    def __init__(self, template: str, *, output_key: str = "text"):
        self.template = template
        self.output_key = output_key

    def invoke(self, state: Mapping[str, Any]) -> Dict[str, Any]:
        try:
            value = self.template.format(**dict(state))
        except Exception:
            # Leave unchanged on missing keys
            value = self.template
        return {self.output_key: value}
