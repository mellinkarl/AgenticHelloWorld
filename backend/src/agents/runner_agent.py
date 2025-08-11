from __future__ import annotations
from typing import Dict, Any

from ..chains.simple_chain import build_simple_chain

class RunnerAgent:
    """
    Agent-1: Thin wrapper around the existing simple chain.
    Input : {"user_input": str}
    Output: {"draft": str}
    """
    def __init__(self, llm):
        self.chain = build_simple_chain(llm)

    def invoke(self, state: Dict[str, Any]) -> Dict[str, Any]:
        user_input: str = state["user_input"]
        draft: str = self.chain.invoke({"user_input": user_input})
        return {"draft": draft}
