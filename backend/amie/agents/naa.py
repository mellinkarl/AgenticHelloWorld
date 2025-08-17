# amie/agents/novelty_agent.py
# Novelty Assessment Agent
# Auther: Harry
# 2025-08-16

import json
from typing import Dict, Any
from langchain_core.runnables import RunnableLambda
from ..state import GraphState

def _noop_novelty(state: GraphState) -> Dict[str, Any]:
    print("===== [NAA] GraphState =====")
    print(json.dumps(state, indent=2, ensure_ascii=False, default=str))
    print("===== END [NAA] =====")

    return {
        "novelty": {
            "novel": True,
            "matches": [],
            "reasoning": "Placeholder novelty reasoning"
        },
        "logs": ["Novelty placeholder ran"]
    }

NOVELTY_A = RunnableLambda(_noop_novelty)
