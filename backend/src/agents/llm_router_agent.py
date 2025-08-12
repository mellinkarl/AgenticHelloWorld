from __future__ import annotations
from typing import Mapping, Dict, Any
from langchain_core.output_parsers import StrOutputParser

from ..prompts.llm_router_prompt import LLM_ROUTER_PROMPT
from ..llm.vertex import get_vertex_chat_model

_VALID = {"PASS", "REFINE", "REFINE_DATE"}

class LLMRouterAgent:
    """
    LLM-based router producing an enum token.
    Input : {"user_input": str, "draft": str}
    Output: {"route": "PASS" | "REFINE" | "REFINE_DATE"}
    """
    def __init__(self, llm=None, *, agent_name: str = "decider"):
        self.llm = llm or get_vertex_chat_model(agent=agent_name)
        self.chain = LLM_ROUTER_PROMPT | self.llm | StrOutputParser()

    def invoke(self, state: Mapping[str, Any]) -> Dict[str, Any]:
        ui = str(state.get("user_input", ""))
        draft = str(state.get("draft", ""))
        route = self.chain.invoke({"user_input": ui, "draft": draft}).strip().upper()
        route = route.replace('"', "").replace("'", "")
        if route not in _VALID:
            route = "REFINE"
        return {"route": route}
