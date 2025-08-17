# amie/agents/idca_agent.py
# Invention Detection & Classification Agent
# Author: Harry
# 2025-08-16

import json
from typing import Dict, Any
from langchain_core.runnables import RunnableLambda
from ..state import GraphState

def _noop_idca(state: GraphState) -> Dict[str, Any]:
    print("===== [IDCA] GraphState =====")
    print(json.dumps(state, indent=2, ensure_ascii=False, default=str))
    print("===== END [IDCA] =====")

    return {
        "idca": {
            "status": "present",
            "summary": "MVP placeholder summary",
            "fields": ["demo"],
            "reasoning": "Placeholder reasoning"
        },
        "logs": ["IDCA placeholder ran"]
    }

INVENTION_D_C = RunnableLambda(_noop_idca)

