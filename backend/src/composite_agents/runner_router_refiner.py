# src/composite_agents/runner_router_refiner.py
from __future__ import annotations
from typing import Dict, Any

from ..core.agent_protocol import Agent
from ..chains.graphs import build_runner_router_refiner_graph, RunnerRouterRefinerState


class RunnerRouterRefinerComposite:
    """
    A composite maintained by a team:
    It wires 3 atomic agents via a hidden graph and exposes a simple `.invoke`.
    """

    def __init__(self, runner: Agent, router: Agent, refiner: Agent):
        self._graph = build_runner_router_refiner_graph(runner, router, refiner)

    def invoke(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Input:  {"user_input": str, "force_refine"?: bool}
        Output: {"text": str}
        """
        # Build a strict TypedDict the compiled graph expects
        s: RunnerRouterRefinerState = {
            "user_input": str(state["user_input"]),
        }
        if "force_refine" in state and state["force_refine"] is not None:
            s["force_refine"] = bool(state["force_refine"])

        return self._graph.invoke(s)
