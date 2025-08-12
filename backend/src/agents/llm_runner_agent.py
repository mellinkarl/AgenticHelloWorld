from __future__ import annotations
from typing import Mapping, Dict, Any, Optional

from langchain_core.output_parsers import StrOutputParser

from ..llm.vertex import get_vertex_chat_model
from ..prompts.base_prompt import BASE_PROMPT

class LLMRunnerAgent:
    """
    Standardize a single LLM call: (prompt -> model -> parse).
    Input : {"user_input": str}
    Output: {"draft": str}
    """
    def __init__(self, llm=None, *, agent_name: Optional[str] = "runner"):
        self.llm = llm or get_vertex_chat_model(agent=agent_name)
        self.chain = BASE_PROMPT | self.llm | StrOutputParser()

    def invoke(self, state: Mapping[str, Any]) -> Dict[str, Any]:
        user_input = str(state.get("user_input", ""))
        draft: str = self.chain.invoke({"user_input": user_input})
        return {"draft": draft}
