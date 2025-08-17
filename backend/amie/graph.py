# amie/graph.py
# Graph wiring for AMIE
# Author: Harry
# 2025-08-16

from __future__ import annotations
from langgraph.graph import StateGraph, END, START
from langgraph.checkpoint.base import BaseCheckpointSaver
from .state import GraphState
from .agents import INGESTION, INVENTION_D_C, NOVELTY_A, AGGREGATION


def build_graph(checkpointer: BaseCheckpointSaver):
    """Build and compile AMIE StateGraph with injected checkpointer."""
    graph = StateGraph(GraphState)

    # --- Register nodes ---
    graph.add_node("ingestion", INGESTION)
    graph.add_node("idca", INVENTION_D_C)
    graph.add_node("novelty", NOVELTY_A)
    graph.add_node("aggregation", AGGREGATION)

    # --- Routing logic ---
    def route_from_idca(state: GraphState) -> str:
        idca = state.get("idca")
        if not idca or "status" not in idca:
            raise ValueError("IDCA missing 'status' field")
        status = idca["status"]
        if status == "present":
            return "novelty"
        elif status in ("implied", "absent"):
            return "aggregation"
        else:
            raise ValueError(f"Unexpected IDCA status: {status}")

    # --- Edges ---
    graph.add_edge(START, "ingestion")
    graph.add_edge("ingestion", "idca")
    graph.add_conditional_edges("idca", route_from_idca)
    graph.add_edge("novelty", "aggregation")
    # graph.add_edge("aggregation", END)


    # ======== DEBUGGING ========
    # Add a final node to print the final state
    from langchain_core.runnables import RunnableLambda
    import json
    def debug_print(state):
        print("===== FINAL GRAPH STATE =====")
        print(json.dumps(state, indent=2, ensure_ascii=False))  # Pretty print JSON
        print("===== END =====")
        return {}

    DEBUG_PRINT = RunnableLambda(debug_print)

    # Wiring: Add a debug node after aggregation
    graph.add_edge("aggregation", "debug_print")
    graph.add_node("debug_print", DEBUG_PRINT)
    graph.add_edge("debug_print", END)

    # Compile with checkpointer
    return graph.compile(checkpointer=checkpointer)
