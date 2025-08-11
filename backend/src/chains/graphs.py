from __future__ import annotations
from typing import (
    Any,
    Dict,
    Optional,
    Literal,
    Mapping,
    TypedDict,
    TYPE_CHECKING,
)

# PEP 655 (3.11+). If you ever run on 3.10, switch to typing_extensions.
try:
    from typing import Required, NotRequired  # Python 3.11+
except Exception:  # pragma: no cover
    from typing_extensions import Required, NotRequired  # type: ignore

from langgraph.graph import StateGraph, END
from langchain_core.runnables import RunnableConfig

# ---- Avoid name collisions & runtime import cost:
# Use a TYPE_CHECKING-only alias for the store type exported by langgraph.
if TYPE_CHECKING:
    from langgraph.store.base import BaseStore as LGBaseStore
else:  # Runtime placeholder (keeps annotations resolvable without importing langgraph.store)
    class LGBaseStore:  # type: ignore[too-many-ancestors]
        ...

from ..core.agent_protocol import Agent


# ---- Typed state with PEP 655 Required/NotRequired ----
class RunnerRouterRefinerState(TypedDict):
    user_input: Required[str]
    draft: NotRequired[str]
    route: NotRequired[Literal["PASS", "REFINE"]]
    text: NotRequired[str]
    force_refine: NotRequired[bool]


def build_runner_router_refiner_graph(
    runner: Agent,
    router: Agent,
    refiner: Agent,
):
    r"""
    Graph:
      entry(user_input) -> runner -> router --PASS--> finalize_pass -> END
                                         \--REFINE-> refiner -> END
    """
    g = StateGraph(RunnerRouterRefinerState)

    # ---- Nodes: Runnable-style signatures ----
    def n_runner(
        state: RunnerRouterRefinerState,
        *,
        config: Optional[RunnableConfig] = None,
        store: Optional[LGBaseStore] = None,
    ) -> Dict[str, Any]:
        return runner.invoke(state)

    def n_router(
        state: RunnerRouterRefinerState,
        *,
        config: Optional[RunnableConfig] = None,
        store: Optional[LGBaseStore] = None,
    ) -> Dict[str, Any]:
        return router.invoke(state)

    def n_refiner(
        state: RunnerRouterRefinerState,
        *,
        config: Optional[RunnableConfig] = None,
        store: Optional[LGBaseStore] = None,
    ) -> Dict[str, Any]:
        return refiner.invoke(state)  # expected {"text": ...}

    def n_finalize_pass(
        state: RunnerRouterRefinerState,
        *,
        config: Optional[RunnableConfig] = None,
        store: Optional[LGBaseStore] = None,
    ) -> Dict[str, Any]:
        return {"text": state.get("draft", "").strip()}

    g.add_node("runner", n_runner)
    g.add_node("router", n_router)
    g.add_node("refiner", n_refiner)
    g.add_node("finalize_pass", n_finalize_pass)

    g.set_entry_point("runner")
    g.add_edge("runner", "router")

    # Pylance warns if we index a NotRequired key; narrow with an assert.
    def route_decision(state: RunnerRouterRefinerState) -> Literal["PASS", "REFINE"]:
        assert "route" in state, "Router must set 'route' before routing."
        return state["route"]

    g.add_conditional_edges(
        "router",
        route_decision,
        {"PASS": "finalize_pass", "REFINE": "refiner"},
    )

    g.add_edge("finalize_pass", END)
    g.add_edge("refiner", END)

    return g.compile()
