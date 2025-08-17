# amie/agents/aggregation_agent.py
# Ingestion Agent
# Auther: Harry
# 2025-08-16

import json
from typing import Dict, Any
from langchain_core.runnables import RunnableLambda
from ..state import GraphState

def _noop_ingestion(state: GraphState) -> Dict[str, Any]:
    print("===== [IA] GraphState =====")
    print(json.dumps(state, indent=2, ensure_ascii=False, default=str))
    print("===== END [IA] =====")

    return {
        "manuscript_text": "This is a sample manuscript.",
        "logs": ["Ingestion placeholder ran"]
    }

INGESTION = RunnableLambda(_noop_ingestion)