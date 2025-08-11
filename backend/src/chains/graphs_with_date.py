from __future__ import annotations
from typing import (
    Any, Dict, Optional, Literal, TypedDict, TYPE_CHECKING
)

# PEP 655
try:
    from typing import Required, NotRequired  # 3.11+
except Exception:  # pragma: no cover
    from typing_extensions import Required, NotRequired  # type: ignore

from langgraph.graph import StateGraph, END
from langchain_core.runnables import RunnableConfig

if TYPE_CHECKING:
    from langgraph.store.base import BaseStore as LGBaseStore
else:
    class LGBaseStore:  # type: ignore
        ...

from ..core.agent_protocol import Agent
from ..tools.date_tool import get_today_iso


class RunnerRouterRefinerWithDateState(TypedDict):
    # Required inputs
    user_input: Required[str]
    # Optional fields progressively filled by the graph
    today: NotRequired[str]
    draft: NotRequired[str]
    route: NotRequired[Literal["PASS", "REFINE"]]
    text: NotRequired[str]
    force_refine: NotRequired[bool]


def build_runner_router_refiner_with_date_graph(
    runner: Agent,
    router: Agent,
    refiner: Agent,
):
    r"""
    Graph (+date & ensure_diff):
      date -> runner -> router --PASS--> finalize_pass -> END
                              \--REFINE-> refiner -> ensure_diff -> END
    """
    g = StateGraph(RunnerRouterRefinerWithDateState)

    # 0) Date node: inject today's date into state
    def n_date(
        state: RunnerRouterRefinerWithDateState,
        *,
        config: Optional[RunnableConfig] = None,
        store: Optional[LGBaseStore] = None,
    ) -> Dict[str, Any]:
        return {"today": get_today_iso()}

    # 1) Runner (draft)
    def n_runner(
        state: RunnerRouterRefinerWithDateState,
        *,
        config: Optional[RunnableConfig] = None,
        store: Optional[LGBaseStore] = None,
    ) -> Dict[str, Any]:
        return runner.invoke(state)

    # 2) Router
    def n_router(
        state: RunnerRouterRefinerWithDateState,
        *,
        config: Optional[RunnableConfig] = None,
        store: Optional[LGBaseStore] = None,
    ) -> Dict[str, Any]:
        return router.invoke(state)

    # 3a) PASS path → finalize to text
    def n_finalize_pass(
        state: RunnerRouterRefinerWithDateState,
        *,
        config: Optional[RunnableConfig] = None,
        store: Optional[LGBaseStore] = None,
    ) -> Dict[str, Any]:
        return {"text": state.get("draft", "").strip()}

    # 3b) REFINE path → refiner
    def n_refiner(
        state: RunnerRouterRefinerWithDateState,
        *,
        config: Optional[RunnableConfig] = None,
        store: Optional[LGBaseStore] = None,
    ) -> Dict[str, Any]:
        # Use the same refiner agent; it ignores 'today' by itself.
        # We'll enforce a difference right after this node.
        return refiner.invoke(state)  # expects {"text": ...}

    # 4) Ensure refined text differs from draft (append date if needed)
    def n_ensure_diff(
        state: RunnerRouterRefinerWithDateState,
        *,
        config: Optional[RunnableConfig] = None,
        store: Optional[LGBaseStore] = None,
    ) -> Dict[str, Any]:
        draft = (state.get("draft") or "").strip()
        text = (state.get("text") or "").strip()
        if text == draft:
            today = state.get("today")
            if today:
                text = f"{text} (as of {today})"
            else:
                text = f"{text} (updated)"
        return {"text": text}

    # Wire nodes
    g.add_node("date", n_date)
    g.add_node("runner", n_runner)
    g.add_node("router", n_router)
    g.add_node("finalize_pass", n_finalize_pass)
    g.add_node("refiner", n_refiner)
    g.add_node("ensure_diff", n_ensure_diff)

    # Entry → date → runner
    g.set_entry_point("date")
    g.add_edge("date", "runner")
    g.add_edge("runner", "router")

    # Branch on router
    def route_decision(state: RunnerRouterRefinerWithDateState) -> Literal["PASS", "REFINE"]:
        assert "route" in state, "Router must set 'route' before routing."
        return state["route"]

    g.add_conditional_edges(
        "router",
        route_decision,
        {
            "PASS": "finalize_pass",
            "REFINE": "refiner",
        },
    )

    # PASS → END ; REFINE → ensure_diff → END
    g.add_edge("finalize_pass", END)
    g.add_edge("refiner", "ensure_diff")
    g.add_edge("ensure_diff", END)

    return g.compile()
