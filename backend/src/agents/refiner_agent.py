from __future__ import annotations
from typing import Mapping, Dict, Any

from ..prompts.refiner_prompt import REFINER_PROMPT

class RefinerAgent:
    """
    refiner_agent: Refines draft to satisfy hard requirements without changing intent.
    Output: {"text": str} 
    """
    def __init__(self, llm, requirements: str = "Must be exactly 'OK.'"):
        self.chain = REFINER_PROMPT | llm
        self.requirements = requirements

    def invoke(self, state: Mapping[str, Any]) -> Dict[str, Any]:
        draft = state.get("draft", "")
        refined = self.chain.invoke({"draft_text": draft, "requirements": self.requirements})
        text = getattr(refined, "content", refined)
        return {"text": text.strip()}