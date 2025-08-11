from __future__ import annotations
from typing import Dict, Any

from ..core.agent_protocol import Agent
from ..chains.graphs_with_date_intent import (
    build_runner_router_refiner_with_date_intent_graph,
    RunnerRouterRefinerDateIntentState,
)

class RunnerRouterRefinerDateIntentComposite:
    """Composite: adds date tool + intent; if need_date=True → '<date> OK'."""
    def __init__(self, runner: Agent, router: Agent, refiner: Agent):
        self._graph = build_runner_router_refiner_with_date_intent_graph(runner, router, refiner)

    def invoke(self, state: Dict[str, Any]) -> Dict[str, Any]:
        s: RunnerRouterRefinerDateIntentState = {"user_input": str(state["user_input"])}
        if "force_refine" in state:
            s["force_refine"] = bool(state["force_refine"])
        return self._graph.invoke(s)
