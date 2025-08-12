from __future__ import annotations
from typing import Mapping, Dict, Any, Optional, Any as _Any

from langchain_core.output_parsers import StrOutputParser

from ..config import get_logger
from ..core.instrumentation import log_invoke_start, log_invoke_end
from ..llm.vertex import get_vertex_chat_model
from ..prompts.base_prompt import BASE_PROMPT  # default if no prompt provided

log = get_logger(__name__)

def _llm_meta(llm: _Any) -> Dict[str, Any]:
    """Best-effort metadata for logging (fields can vary across LLM wrappers)."""
    return {
        "model": getattr(llm, "model", getattr(llm, "model_name", None)),
        "temperature": getattr(llm, "temperature", None),
        "max_output_tokens": getattr(llm, "max_output_tokens", None),
        "response_mime_type": getattr(llm, "response_mime_type", None),
    }

class LLMRunnerAgent:
    """
    Run a single LLM call with a standard chain:
        prompt (ChatPromptTemplate) → model (Vertex) → StrOutputParser → "draft"

    # Contract
    - Input state:  {"user_input": str}
    - Output state: {"draft": str}
      (Always a plain string thanks to StrOutputParser.)

    # Prompt injection (recommended pattern)
    Pass a custom `prompt` to override the default BASE_PROMPT, e.g.:
        from src.prompts import get_prompt
        p = get_prompt("runner/personal")
        agent = LLMRunnerAgent(prompt=p)

    # Config & logging
    - The underlying model is selected via `agent_name` (e.g., "runner") and
      created by get_vertex_chat_model(). Per-agent params come from config.
    - log_invoke_start/log_invoke_end wrap calls with structured JSON logs:
      previews of inputs/outputs, elapsed ms, and LLM metadata from `_llm_meta`.

    # Async
    - `ainvoke` uses the chain's native async (`.ainvoke`) for true non-blocking I/O.
    - Use when serving concurrent requests or composing async pipelines.

    # Error surface
    - Exceptions from the model/chain propagate to the caller (no internal try/except).
      This is intentional so the API layer can apply uniform error handling.
    """
    def __init__(
        self,
        llm=None,
        *,
        agent_name: Optional[str] = "runner",
        prompt=None,  # optional: inject a custom ChatPromptTemplate; defaults to BASE_PROMPT
    ):
        # Model: either provided externally or built from config profile "agent_name"
        self.llm = llm or get_vertex_chat_model(agent=agent_name)

        # Prompt: default global prompt unless an explicit one is injected by caller
        self.prompt = prompt or BASE_PROMPT

        # Chain: prompt → LLM → string parser (guarantees str output for "draft")
        self.chain = self.prompt | self.llm | StrOutputParser()

        # Capture LLM configuration for observability (added to start/end logs)
        self.meta = _llm_meta(self.llm)

    def invoke(self, state: Mapping[str, Any]) -> Dict[str, Any]:
        """
        Synchronous execution.
        1) Logs "start" with input previews and LLM metadata.
        2) Extracts `user_input` from state (default empty string).
        3) Runs the chain synchronously to produce `draft: str`.
        4) Logs "end" with output preview and duration.
        5) Returns {"draft": draft}.
        """
        t0 = log_invoke_start(log, "LLMRunnerAgent", state, extra=self.meta)
        user_input = str(state.get("user_input", ""))  # tolerate missing/None
        draft: str = self.chain.invoke({"user_input": user_input})
        out = {"draft": draft}
        log_invoke_end(log, "LLMRunnerAgent", t0, out, extra=self.meta)
        return out

    async def ainvoke(self, state: Mapping[str, Any]) -> Dict[str, Any]:
        """
        Asynchronous execution (true async path).
        Mirrors `invoke` but awaits `chain.ainvoke(...)`. Use in async servers/composites.
        """
        t0 = log_invoke_start(log, "LLMRunnerAgent", state, extra=self.meta)
        user_input = str(state.get("user_input", ""))  # tolerate missing/None
        draft: str = await self.chain.ainvoke({"user_input": user_input})
        out = {"draft": draft}
        log_invoke_end(log, "LLMRunnerAgent", t0, out, extra=self.meta)
        return out
