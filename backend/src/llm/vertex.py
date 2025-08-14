from __future__ import annotations
from typing import Optional, Dict, Any

from langchain_core.runnables import Runnable
from langchain_google_vertexai import ChatVertexAI
from ..config.config import Config

# Ctor allow-list for your adapter version (keep minimal & safe)
_CTOR_ALLOWED = {
    "project",
    "location",
    "model",
    "temperature",
    "top_p",
    "top_k",
    "max_output_tokens",
    "response_mime_type",
    # NOTE: credentials injected separately
}

# Call-time alias map (YAML → adapter runtime kwarg)
_CALL_ALIASES = {
    "timeout_s": "request_timeout",   # ctor doesn't accept; bind at call-time
    # add more runtime-only mappings here if needed
}

def _split_kwargs(raw: Dict[str, Any]) -> tuple[Dict[str, Any], Dict[str, Any]]:
    """
    Split config kwargs into:
      - ctor_kwargs: passed to ChatVertexAI(...)
      - call_kwargs: bound via llm.bind(**call_kwargs)
    Drops unknown or None values safely.
    """
    ctor: Dict[str, Any] = {}
    call: Dict[str, Any] = {}
    for k, v in raw.items():
        if v is None:
            continue
        if k in _CTOR_ALLOWED:
            ctor[k] = v
        elif k in _CALL_ALIASES:
            call[_CALL_ALIASES[k]] = v
        # silently drop unsupported keys (e.g., candidate_count, system_instruction, api_endpoint)
    return ctor, call

def get_vertex_chat_model(
    cfg: Optional[Config] = None,
    agent: Optional[str] = None,
    **overrides: Dict[str, Any],
) -> Runnable:
    """
    Build a Vertex chat LLM runnable:
      global defaults <- agents.<agent> <- **overrides
    Return value is a Runnable (ChatVertexAI or a bound wrapper) ready for LCEL: prompt | llm | parser.
    """
    cfg = cfg or Config.load()

    # Wire env (ADC vs local SA)
    cfg.apply_google_env()

    # Load explicit creds if any (None under ADC)
    creds = cfg.load_credentials()

    # Initialize vertex client (use creds if present)
    cfg.init_vertex(credentials=creds)

    # Prepare kwargs
    raw = cfg.llm_kwargs(agent=agent, **overrides)
    ctor_kwargs, call_kwargs = _split_kwargs(raw)

    # Construct adapter
    llm = ChatVertexAI(credentials=creds, **ctor_kwargs)

    # Bind runtime-only kwargs (e.g., request_timeout)
    if call_kwargs:
        llm = llm.bind(**call_kwargs)

    return llm
