from __future__ import annotations
from typing import Optional, Dict, Any

from langchain_google_vertexai import ChatVertexAI
from ..config.config import Config

# Allow-list for your current langchain-google-vertexai version
_ALLOWED_KW = {
    "project",
    "location",
    "model",
    "temperature",
    "top_p",
    "top_k",
    "max_output_tokens",
    "response_mime_type",
    # NOTE: we pass 'credentials' separately to the ctor, not via kwargs
}
_ALIAS_MAP = {
    # YAML uses timeout_s; LangChain wants request_timeout
    "timeout_s": "request_timeout",
}

def _sanitize_model_kwargs(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Drop unknown keys and apply a few aliases so the adapter won't warn."""
    out: Dict[str, Any] = {}
    for k, v in raw.items():
        if v is None:
            continue
        if k in _ALLOWED_KW:
            out[k] = v
        elif k in _ALIAS_MAP:
            out[_ALIAS_MAP[k]] = v
        # else: silently drop (e.g., candidate_count, system_instruction, api_endpoint)
    return out

def get_vertex_chat_model(
    cfg: Optional[Config] = None,
    agent: Optional[str] = None,
    **overrides: Dict[str, Any],
) -> ChatVertexAI:
    """
    Build ChatVertexAI with:
      global defaults <- agents.<agent> overrides <- runtime **overrides
    Then sanitize to only pass adapter-supported kwargs.
    """
    cfg = cfg or Config.load()

    # Wire env (ADC/local SA), get explicit creds if any, then init Vertex
    cfg.apply_google_env()
    creds = cfg.load_credentials()
    cfg.init_vertex(credentials=creds)

    raw = cfg.llm_kwargs(agent=agent, **overrides)
    kwargs = _sanitize_model_kwargs(raw)

    # Construct adapter; inject credentials explicitly if present
    return ChatVertexAI(credentials=creds, **kwargs)
