from __future__ import annotations
from typing import Protocol, Mapping, Dict, Any

class Agent(Protocol):
    """Minimal contract every agent must implement."""
    def invoke(self, state: Mapping[str, Any]) -> Dict[str, Any]:
        ...