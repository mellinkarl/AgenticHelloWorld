from __future__ import annotations
from typing import Optional, Dict, Any

from langchain_google_vertexai import ChatVertexAI
from ..config.config import Config


def get_vertex_chat_model(
    cfg: Optional[Config] = None,
    agent: Optional[str] = None,
    **overrides: Dict[str, Any],
) -> ChatVertexAI:
    """
    Create a ChatVertexAI with config + (optional) agent-level + runtime overrides.
    Precedence: global <- agents.<agent> <- **overrides
    """
    cfg = cfg or Config.load()

    # 1) 环境变量布线（ADC / 本地 key）
    cfg.apply_google_env()

    # 2) 取显式凭证（ADC 下为 None）
    creds = cfg.load_credentials()

    # 3) 初始化 Vertex 客户端（若有显式凭证则带上）
    cfg.init_vertex(credentials=creds)

    # 4) 组装模型参数（移除 None）
    kwargs = {k: v for k, v in cfg.llm_kwargs(agent=agent, **overrides).items() if v is not None}

    # 5) 传给 LangChain 适配器；有 creds 则显式注入
    return ChatVertexAI(credentials=creds, **kwargs)
