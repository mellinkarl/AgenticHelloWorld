from __future__ import annotations
from typing import Any, Dict, Optional, Literal, TypedDict, TYPE_CHECKING

# PEP 655 (Python 3.11+). If you run 3.10, switch to typing_extensions.
try:
    from typing import Required, NotRequired
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


class RunnerRouterRefinerDateIntentState(TypedDict):
    # Required input
    user_input: Required[str]
    # Filled by nodes
    today: NotRequired[str]
    need_date: NotRequired[bool]
    draft: NotRequired[str]
    route: NotRequired[Literal["PASS", "REFINE", "REFINE_DATE"]]
    text: NotRequired[str]
    force_refine: NotRequired[bool]


def _detect_need_date(text: str) -> bool:
    t = text.lower()
    # Simple heuristic; extend as needed
    return any(k in t for k in ["date", "today", "current date"])


def build_runner_router_refiner_with_date_intent_graph(
    runner: Agent,
    router: Agent,
    refiner: Agent,
):
    r"""
    Graph (+date tool + intent + date-refine branch):
      date -> intent -> runner -> router
                               ├─ PASS        → finalize_pass → END
                               ├─ REFINE_DATE → date_refiner  → END
                               └─ REFINE      → refiner       → END
    """
    g = StateGraph(RunnerRouterRefinerDateIntentState)

    # 0) date
    def n_date(
        state: RunnerRouterRefinerDateIntentState, *,
        config: Optional[RunnableConfig] = None,
        store: Optional[LGBaseStore] = None,
    ) -> Dict[str, Any]:
        return {"today": get_today_iso()}

    # 1) intent: set need_date based on user_input
    def n_intent(
        state: RunnerRouterRefinerDateIntentState, *,
        config: Optional[RunnableConfig] = None,
        store: Optional[LGBaseStore] = None,
    ) -> Dict[str, Any]:
        ui = state["user_input"]
        return {"need_date": _detect_need_date(ui)}

    # 2) runner
    def n_runner(
        state: RunnerRouterRefinerDateIntentState, *,
        config: Optional[RunnableConfig] = None,
        store: Optional[LGBaseStore] = None,
    ) -> Dict[str, Any]:
        return runner.invoke(state)

    # 3) router (override with REFINE_DATE if needed)
    def n_router(
        state: RunnerRouterRefinerDateIntentState, *,
        config: Optional[RunnableConfig] = None,
        store: Optional[LGBaseStore] = None,
    ) -> Dict[str, Any]:
        # Base route from existing RouterAgent
        base = router.invoke(state)  # {"route": "PASS" | "REFINE"}
        route = base.get("route", "REFINE")
        if state.get("need_date"):
            route = "REFINE_DATE"
        return {"route": route}

    # 4a) PASS
    def n_finalize_pass(
        state: RunnerRouterRefinerDateIntentState, *,
        config: Optional[RunnableConfig] = None,
        store: Optional[LGBaseStore] = None,
    ) -> Dict[str, Any]:
        return {"text": state.get("draft", "").strip()}

    # 4b) REFINE_DATE → tool-based deterministic output: "<YYYY-MM-DD> OK"
    def n_date_refiner(
        state: RunnerRouterRefinerDateIntentState, *,
        config: Optional[RunnableConfig] = None,
        store: Optional[LGBaseStore] = None,
    ) -> Dict[str, Any]:
        today = state.get("today") or get_today_iso()
        return {"text": f"{today} OK"}

    # 4c) REFINE → normal refiner agent
    def n_refiner(
        state: RunnerRouterRefinerDateIntentState, *,
        config: Optional[RunnableConfig] = None,
        store: Optional[LGBaseStore] = None,
    ) -> Dict[str, Any]:
        return refiner.invoke(state)  # {"text": ...}

    # Wire nodes
    g.add_node("date", n_date)
    g.add_node("intent", n_intent)
    g.add_node("runner", n_runner)
    g.add_node("router", n_router)
    g.add_node("finalize_pass", n_finalize_pass)
    g.add_node("date_refiner", n_date_refiner)
    g.add_node("refiner", n_refiner)

    g.set_entry_point("date")
    g.add_edge("date", "intent")
    g.add_edge("intent", "runner")
    g.add_edge("runner", "router")

    def route_decision(state: RunnerRouterRefinerDateIntentState) -> Literal["PASS", "REFINE", "REFINE_DATE"]:
        assert "route" in state, "Router must set 'route'."
        return state["route"]

    g.add_conditional_edges(
        "router",
        route_decision,
        {
            "PASS": "finalize_pass",
            "REFINE_DATE": "date_refiner",
            "REFINE": "refiner",
        },
    )

    g.add_edge("finalize_pass", END)
    g.add_edge("date_refiner", END)
    g.add_edge("refiner", END)

    return g.compile()
