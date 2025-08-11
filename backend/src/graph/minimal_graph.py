from __future__ import annotations
from typing import TypedDict, Literal, Optional

from langgraph.graph import StateGraph, END

from ..agents.runner_agent import RunnerAgent
from ..agents.router_agent import RouterAgent
from ..agents.refiner_agent import RefinerAgent

class GraphState(TypedDict, total=False):
    user_input: str
    draft: str
    route: Literal["PASS", "REFINE"]
    text: str                 # final output
    force_refine: Optional[bool]

def build_minimal_graph(runner: RunnerAgent, router: RouterAgent, refiner: RefinerAgent):
    """
    Graph:
      entry(user_input) -> runner -> router --PASS--> finalize_pass -> END
                                         \--REFINE-> refiner -> END
    """
    g = StateGraph(GraphState)

    def n_runner(s: GraphState) -> GraphState:
        return runner.invoke(s)

    def n_router(s: GraphState) -> GraphState:
        return router.invoke(s)

    def n_refiner(s: GraphState) -> GraphState:
        return refiner.invoke(s)  # returns {"text": ...}

    def n_finalize_pass(s: GraphState) -> GraphState:
        # Normalize PASS path to final {"text": ...}
        return {"text": s.get("draft", "")}

    g.add_node("runner", n_runner)
    g.add_node("router", n_router)
    g.add_node("refiner", n_refiner)
    g.add_node("finalize_pass", n_finalize_pass)

    g.set_entry_point("runner")
    g.add_edge("runner", "router")

    def route_decision(s: GraphState) -> str:
        return s["route"]

    g.add_conditional_edges(
        "router",
        route_decision,
        {
            "PASS": "finalize_pass",
            "REFINE": "refiner",
        },
    )

    g.add_edge("finalize_pass", END)
    g.add_edge("refiner", END)

    return g.compile()

# Tiny local unit test for router logic (no network)
def _local_rule_unit_test():
    r = RouterAgent(require_exact="OK.")
    assert r.invoke({"draft": "OK."})["route"] == "PASS"
    assert r.invoke({"draft": "ok."})["route"] == "REFINE"
    assert r.invoke({"draft": "OK.", "force_refine": True})["route"] == "REFINE"
