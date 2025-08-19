# amie/graph.py
# Graph wiring with conditional routing via artifacts.idca.status

from __future__ import annotations
from langgraph.graph import StateGraph, END
from .state import GraphState
from .agents import INGESTION, INVENTION_D_C, NOVELTY_A, AGGREGATION

# Node names (string ids used in edges/conditions)
NODE_INGESTION   = "ingestion"
NODE_IDCA        = "idca"
NODE_NOVELTY     = "novelty"
NODE_AGGREGATION = "aggregation"


def route_from_idca(state: GraphState) -> str:
    """
    Decide next hop based on artifacts.idca.status.

    Returns one of:
      - "novelty"      -> run Novelty Assessment
      - "aggregation"  -> skip novelty, go straight to Aggregation
    """
    artifacts = state.get("artifacts") or {}
    idca = artifacts.get("idca") or {}
    status = idca.get("status")

    if status is None:
        raise ValueError("artifacts.idca.status is missing")

    if status == "present":
        return NODE_NOVELTY
    elif status in ("implied", "absent"):
        return NODE_AGGREGATION
    else:
        raise ValueError(f"Unexpected IDCA status: {status!r}")


def build_graph():
    """
    Build & compile the AMIE LangGraph:
      ingestion -> idca -> (novelty | aggregation) -> aggregation -> END
    The conditional branch is decided by `route_from_idca`.
    """
    g = StateGraph(GraphState)

    # Register nodes with functions exported by amie/agents/__init__.py
    g.add_node(NODE_INGESTION,   INGESTION)     # ia
    g.add_node(NODE_IDCA,        INVENTION_D_C) # idca
    g.add_node(NODE_NOVELTY,     NOVELTY_A)     # naa
    g.add_node(NODE_AGGREGATION, AGGREGATION)   # aa

    # Entry
    g.set_entry_point(NODE_INGESTION)

    # Linear edge: ingestion -> idca
    g.add_edge(NODE_INGESTION, NODE_IDCA)

    # Conditional route after IDCA
    g.add_conditional_edges(
        NODE_IDCA,
        route_from_idca,
        {
            NODE_NOVELTY: NODE_NOVELTY,
            NODE_AGGREGATION: NODE_AGGREGATION,
        },
    )

    # If novelty runs, go to aggregation next
    g.add_edge(NODE_NOVELTY, NODE_AGGREGATION)

    # Finish
    g.add_edge(NODE_AGGREGATION, END)

    return g.compile()
