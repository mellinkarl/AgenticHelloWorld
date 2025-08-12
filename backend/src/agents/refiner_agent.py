from __future__ import annotations
from typing import Mapping, Dict, Any, Optional, Any as _Any

from langchain_core.output_parsers import StrOutputParser

from ..config import get_logger
from ..core.instrumentation import log_invoke_start, log_invoke_end
from ..prompts.refiner_prompt import REFINER_PROMPT
from ..llm.vertex import get_vertex_chat_model

log = get_logger(__name__)

def _llm_meta(llm: _Any) -> Dict[str, Any]:
    """
    Extract model configuration for logging.
    Uses a best-effort approach to handle different attribute names
    across LLM implementations.
    """
    return {
        "model": getattr(llm, "model", getattr(llm, "model_name", None)),
        "temperature": getattr(llm, "temperature", None),
        "max_output_tokens": getattr(llm, "max_output_tokens", None),
        "response_mime_type": getattr(llm, "response_mime_type", None),
    }

class RefinerAgent:
    """
    A lightweight refinement agent that keeps the original intent
    of the text but improves clarity, formatting, and completeness.

    Input state:
        {
            "draft": str   # The text to be refined
        }

    Output state:
        {
            "text": str    # The refined text
        }
    """

    def __init__(
        self,
        llm=None,
        requirements: str = "Keep intent; improve clarity only.",
        *,
        agent_name: str = "refiner"
    ):
        """
        Args:
            llm:
                Optional pre-configured LLM instance. If not provided,
                a Vertex AI chat model is loaded.
            requirements:
                A string describing refinement rules (passed into the prompt).
            agent_name:
                Profile name for selecting LLM configuration.
        """
        # Use provided LLM or load default Vertex model
        self.llm = llm or get_vertex_chat_model(agent=agent_name)

        # Build the chain: refinement prompt → LLM → string output parser
        self.chain = REFINER_PROMPT | self.llm | StrOutputParser()

        # Store requirements and LLM configuration for logging
        self.requirements = requirements
        self.meta = _llm_meta(self.llm)

    def invoke(self, state: Mapping[str, Any]) -> Dict[str, Any]:
        """
        Run refinement synchronously.
        - Logs start time and metadata
        - Passes the draft text and refinement requirements into the LLM
        - Logs execution duration and output
        """
        t0 = log_invoke_start(log, "RefinerAgent", state, extra=self.meta)

        draft = str(state.get("draft", ""))

        # Execute refinement chain synchronously
        text: str = self.chain.invoke({
            "draft_text": draft,
            "requirements": self.requirements
        })

        out = {"text": text}

        log_invoke_end(log, "RefinerAgent", t0, out, extra=self.meta)
        return out

    async def ainvoke(self, state: Mapping[str, Any]) -> Dict[str, Any]:
        """
        Run refinement asynchronously using the LLM's async API.
        """
        t0 = log_invoke_start(log, "RefinerAgent", state, extra=self.meta)

        draft = str(state.get("draft", ""))

        # Execute refinement chain asynchronously
        text: str = await self.chain.ainvoke({
            "draft_text": draft,
            "requirements": self.requirements
        })

        out = {"text": text}

        log_invoke_end(log, "RefinerAgent", t0, out, extra=self.meta)
        return out
