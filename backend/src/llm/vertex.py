from __future__ import annotations
from typing import Optional

from langchain_google_vertexai import ChatVertexAI
from ..config import Config, USE_ADC


def get_vertex_chat_model(cfg: Optional[Config] = None, agent: Optional[str] = None, **overrides) -> ChatVertexAI:
    """
    Create a ChatVertexAI with config + (optional) agent-level + runtime overrides.
    - Honors USE_ADC (no explicit credentials) or loads local service account.
    - Always sets response_mime_type.
    """
    cfg = cfg or Config.load()
    cfg.apply_google_env()
    cfg.init_vertex()

    creds = None if USE_ADC else cfg.load_credentials()
    kwargs = cfg.llm_kwargs(agent=agent, **overrides)
    return ChatVertexAI(credentials=creds, **kwargs)
