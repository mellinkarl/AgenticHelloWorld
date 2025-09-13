# amie/agents/naa.py
# Novelty Assessment Agent (JSON-structured, IDCA-style LLM calling)
# Author: Harry
# 2025-09-14

from __future__ import annotations

import json
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

from google import genai
from google.genai import types
from langchain_core.runnables import RunnableLambda

from ..state import GraphState
from .schema.naa_schema import (
    SCHEMA_INVENTION_TYPE,
    SCHEMA_METHOD_DETAILS,
    SCHEMA_PHYSICAL_DETAILS,
    SCHEMA_QUERY_SYNTH,
    SCHEMA_COMPARE,
    SCHEMA_SCORE,
    SCHEMA_OVERALL,
)

# 选一个默认文本模型（与 IDCA 风格一致：轻量快速）
MODEL_TEXT_DEFAULT = "gemini-2.0-flash-lite-001"

# ---------------------------------------------------------------------
# Dummy（保留以便回归测试）
# ---------------------------------------------------------------------

def naa_node_dummy(state: GraphState, config=None) -> Dict[str, Any]:
    novelty_art = {
        "integrated": [],
        "detailed_checks": [],
        "invention_type": "method",
        "invention_details": {
            "method_steps": [],
        },
        "queries": [{"q": "site:patents.google.com 3D printed robotic arm capstan drive", "why": "core features"}],
        "model_version": "naa-dummy-0",
        "generated_at": "yy-mm-dd-hh-mm-ss",
    }
    return {
        "runtime": {"naa": {"status": "FINISHED", "route": []}},
        "artifacts": {"naa": novelty_art},
        "internals": {"naa": []},
        "message": "naa mock finished",
    }


# 导出为 Runnable
NOVELTY_A = RunnableLambda(naa_node_dummy)
