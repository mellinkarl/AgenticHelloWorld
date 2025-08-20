# amie/agents/aggregation_agent.py
# Aggregation Agent
# Auther: Harry
# 2025-08-18

import json
from typing import Dict, Any
from langchain_core.runnables import RunnableLambda
from ..state import GraphState

def aa_node(state: GraphState) -> Dict[str, Any]:
    """
    Aggregation Agent (dummy):
    - Reads artifacts from IDCA / NAA and composes a final JSON report.
    """
    arts = state.get("artifacts") or {}
    idca = arts.get("idca") or {}
    novelty = arts.get("novelty") or {}
    ingestion = arts.get("ingestion") or {}

    report = {
        "ingestion": ingestion,
        "idca": idca,
        "novelty": novelty,
        "verdict": "UNDECIDED (dummy)",  # Your real logic would set a final flag.
    }
    aa_cache = {
        "weights": {"idca": 0.5, "naa": 0.5},
        "merge_policy": "dummy-avg",
    }

    return {
        "artifacts": {"report": report},
        "internals": {"aa": aa_cache},
        "logs": ["AA: dummy aggregation complete."],
    }

AGGREGATION = RunnableLambda(aa_node)

