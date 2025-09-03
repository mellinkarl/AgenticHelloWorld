# amie/agents/novelty_agent.py
# Novelty Assessment Agent
# Auther: Harry
# 2025-08-18

import json
from typing import Dict, Any
from langchain_core.runnables import RunnableLambda
from ..state import GraphState

def naa_node_dummy(state: GraphState) -> Dict[str, Any]:
    """
    Novelty Assessment Agent (dummy):
    - Pretends to retrieve some matches and outputs a minimal novelty artifact.
    """
    novelty_art = {
        "novel": "undetermined",
        "matches": [{"title": "Dummy prior art", "score": 0.42}],
        "reasoning": "Dummy NAA executed",
    }
    naa_cache = {
        "retrieved": 1,
        "model_version": "naa-dummy-0",
    }

    return {
        "artifacts": {"novelty": novelty_art},
        "internals": {"naa": naa_cache},
        "logs": ["NAA: dummy novelty assessment done."],
    }

NOVELTY_A = RunnableLambda(naa_node_dummy)
