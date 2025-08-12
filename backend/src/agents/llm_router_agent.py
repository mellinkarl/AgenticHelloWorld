from __future__ import annotations
from typing import Mapping, Dict, Any, Optional, Any as _Any

from langchain_core.output_parsers import StrOutputParser

from ..config import get_logger
from ..core.instrumentation import log_invoke_start, log_invoke_end
from ..llm.vertex import get_vertex_chat_model
from ..prompts.llm_router_prompt import LLM_ROUTER_PROMPT

# Allowed route values
_VALID = {"PASS", "REFINE", "REFINE_DATE"}

log = get_logger(__name__)

def _llm_meta(llm: _Any) -> Dict[str, Any]:
    """
    Extract model configuration info for logging.
    Handles variations in attribute names across LLM implementations.
    """
    return {
        "model": getattr(llm, "model", getattr(llm, "model_name", None)),
        "temperature": getattr(llm, "temperature", None),
        "max_output_tokens": getattr(llm, "max_output_tokens", None),
        "response_mime_type": getattr(llm, "response_mime_type", None),
    }

def _normalize_route(s: str) -> str:
    """
    Standardize the raw LLM output to a valid route token.
    - Strips whitespace and quotes.
    - Converts to uppercase.
    - Falls back to "REFINE" if the result is not in _VALID.
    """
    r = s.strip().upper().replace('"', "").replace("'", "")
    return r if r in _VALID else "REFINE"

class LLMRouterAgent:
    """
    An LLM-based router that decides a routing enum value
    based on the original user input and a draft response.

    Input state:
        {
            "user_input": str,   # The original prompt or question
            "draft": str         # The current draft output
        }

    Output state:
        {
            "route": "PASS" | "REFINE" | "REFINE_DATE",  # Routing decision
            "raw": str                                   # Raw unprocessed LLM output
        }
    """

    def __init__(self, llm=None, *, agent_name: str = "decider"):
        """
        Args:
            llm:
                Optional pre-configured LLM instance.
                Defaults to a Vertex AI Chat model configured as "decider".
            agent_name:
                Model configuration profile name for `get_vertex_chat_model`.
        """
        self.llm = llm or get_vertex_chat_model(agent=agent_name)

        # Build the chain: Router prompt → LLM → Parse to string
        self.chain = LLM_ROUTER_PROMPT | self.llm | StrOutputParser()

        # Capture LLM configuration for logging
        self.meta = _llm_meta(self.llm)

    def invoke(self, state: Mapping[str, Any]) -> Dict[str, Any]:
        """
        Run the routing decision synchronously.
        Logs start/end events with model metadata and execution time.
        """
        t0 = log_invoke_start(log, "LLMRouterAgent", state, extra=self.meta)

        # Extract inputs for the LLM
        ui = str(state.get("user_input", ""))
        draft = str(state.get("draft", ""))

        # Get raw route decision from the LLM
        raw: str = self.chain.invoke({"user_input": ui, "draft": draft})

        # Normalize into a valid route
        route = _normalize_route(raw)

        out = {"route": route, "raw": raw}
        log_invoke_end(log, "LLMRouterAgent", t0, out, extra=self.meta)
        return out

    async def ainvoke(self, state: Mapping[str, Any]) -> Dict[str, Any]:
        """
        Run the routing decision asynchronously using the LLM's async API.
        """
        t0 = log_invoke_start(log, "LLMRouterAgent", state, extra=self.meta)

        ui = str(state.get("user_input", ""))
        draft = str(state.get("draft", ""))

        raw: str = await self.chain.ainvoke({"user_input": ui, "draft": draft})
        route = _normalize_route(raw)

        out = {"route": route, "raw": raw}
        log_invoke_end(log, "LLMRouterAgent", t0, out, extra=self.meta)
        return out
