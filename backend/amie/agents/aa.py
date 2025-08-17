# amie/agents/aggregation_agent.py
# Aggregation Agent
# Auther: Harry
# 2025-08-16

import json
from typing import Dict, Any
from langchain_core.runnables import RunnableLambda
from ..state import GraphState

def _noop_aggregation(state: GraphState) -> Dict[str, Any]:
    print("===== [AA] FINAL GraphState =====")
    print(json.dumps(state, indent=2, ensure_ascii=False, default=str))
    print("===== END [AA] =====")

    return {
        "report": {
            "status": "MVP",
            "note": "Pipeline skeleton executed successfully"
        },
        "logs": ["Aggregation placeholder ran"]
    }

AGGREGATION = RunnableLambda(_noop_aggregation)

