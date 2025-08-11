from __future__ import annotations
from typing import Dict, Any

from ..core.agent_protocol import Agent
from ..chains.graphs_with_date import (
    build_runner_router_refiner_with_date_graph,
    RunnerRouterRefinerWithDateState,
)


class RunnerRouterRefinerWithDateComposite:
    """Composite that adds a 'date' tool and guarantees refiner output differs."""
    def __init__(self, runner: Agent, router: Agent, refiner: Agent):
        self._graph = build_runner_router_refiner_with_date_graph(runner, router, refiner)

    def invoke(self, state: Dict[str, Any]) -> Dict[str, Any]:
        s: RunnerRouterRefinerWithDateState = {"user_input": str(state["user_input"])}
        if "force_refine" in state:
            s["force_refine"] = bool(state["force_refine"])
        return self._graph.invoke(s)
