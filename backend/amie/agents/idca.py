# amie/agents/idca_agent.py
# Invention Detection & Classification Agent
# Author: Harry
# 2025-08-18

import json
from typing import Dict, Any
from langchain_core.runnables import RunnableLambda
from ..state import GraphState

def idca_node_dummy(state: GraphState) -> Dict[str, Any]:
    """
    Invention Detection & Classification Agent (dummy):
    - Reads IA internals (normalized_uri) just to demonstrate cross-agent read.
    - Emits a tiny 'idca' artifact.
    """
    ia_cache = (state.get("internals") or {}).get("ia") or {}
    src = ia_cache.get("normalized_uri", state.get("doc_uri"))

    idca_art = {
        "status": "implied",          # present | absent | implied (dummy)
        "summary": "Dummy IDCA summary",
        "fields": ["Robotics", "Perception"],
        "reasoning": f"Analyzed source: {src}",
    }
    idca_cache = {
        "model_version": "idca-dummy-0",
        "debug": "ok",
    }

    return {
        "artifacts": {"idca": idca_art},
        "internals": {"idca": idca_cache},
        "logs": ["IDCA: dummy classification done."],
    }

INVENTION_D_C = RunnableLambda(idca_node_dummy)

