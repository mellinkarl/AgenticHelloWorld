# amie/state.py
# AMIE graph state
# Author: Harry
# 2025-08-16

from __future__ import annotations

import operator
from typing import Any, Dict, List, Optional, Literal
from typing_extensions import Annotated, TypedDict
from langchain.schema import Document
from langchain_core.messages import AnyMessage

# =============================== MVP COMMENTS ===============================
# Minimal usage rules:
# 1) Business outputs are under `artifacts` and are agent-scoped:
#       artifacts = { "ia": {...}, "idca": {...}, "naa": {...}, "aa": {...}, "report": {...} }
# 2) Per-agent caches are under `internals`:
#       internals = { "ia": {...}, "idca": {...}, "naa": {...}, "aa": {...} }
# 3) Every agent has a `runtime` entry with a RunStatus (default "PENDING") and a route list
#    (default empty, meaning no special restrictions).
# 4) Nodes MUST return PATCHES; do NOT mutate state in-place.
# 5) Reducers:
#       - artifacts / internals / runtime use dict-union (operator.or_) to merge branches
#       - logs / errors are append-only (operator.add)
# 6) Frontend should only receive the final `artifacts.report`. Use `frontend_view(state)`.

# ---- shared enums ----
RunStatus = Literal["PENDING", "RUNNING", "FAILED", "FINISHED"]

# ---- agent-scoped sections ----
class Internals(TypedDict, total=False):
    ia: Dict[str, Any]
    idca: Dict[str, Any]
    naa: Dict[str, Any]
    aa: Dict[str, Any]

class Artifacts(TypedDict, total=False):
    ia: Dict[str, Any]
    idca: Dict[str, Any]
    naa: Dict[str, Any]
    aa: Dict[str, Any]
    report: Dict[str, Any]   # final, aggregated, UI-facing

class AgentRuntime(TypedDict, total=False):
    status: RunStatus            # per-agent run status, defaults to "PENDING"
    route: List[str]             # optional routing hints/notes (default [])

class Runtime(TypedDict, total=False):
    ia: AgentRuntime
    idca: AgentRuntime
    naa: AgentRuntime
    aa: AgentRuntime

class GraphState(TypedDict, total=False):
    """The single state object passed across LangGraph nodes and persisted by the API."""

    # ---- LangChain / RAG basics ----
    messages: Annotated[List[AnyMessage], operator.add]
    documents: List[Document]
    generation: Any
    attempted_generations: int

    # ---- Invocation basics (injected by API) ----
    request_id: str
    doc_uri: str
    metadata: Dict[str, Any]

    # ---- Orchestration / global UI-facing ----
    status: RunStatus            # global run status: PENDING/RUNNING/FAILED/FINISHED
    created_at: str              # ISO 8601
    updated_at: str              # ISO 8601

    # ---- Agent runtime (per-agent status + route), branch-safe union ----
    runtime: Annotated[Runtime, operator.or_]

    # ---- Business-facing outputs (agent-scoped + report), branch-safe union ----
    artifacts: Annotated[Artifacts, operator.or_]

    # ---- Per-agent caches (cross-agent readable; only owner writes), branch-safe union ----
    internals: Annotated[Internals, operator.or_]

    # ---- Diagnostics (append-only) ----
    errors: Annotated[List[str], operator.add]
    logs:   Annotated[List[str], operator.add]


# ============================= DETAIL COMMENTS =============================
# Why dict-union on artifacts/internals/runtime?
# - LangGraph merges node results by reducing channel values. Using operator.or_ at top level
#   lets independent keys co-exist (e.g., artifacts["idca"] and artifacts["naa"]).
# - Conflict on the same key resolves to "last writer wins", which is fine because each agent
#   only writes its own subkey (ia/idca/naa/aa).

# Recommended shapes (non-binding):
# artifacts["ia"]     = {"doc_uri": "...", "storage": "local|gcs", "checksum": "...", "mime": "..."}
# artifacts["idca"]   = {"status": "present|absent|implied", "summary": str, "fields": [str], "reasoning": str}
# artifacts["naa"]    = {"novel": bool|"undetermined", "matches": [...], "reasoning": str}
# artifacts["aa"]     = {"merge_notes": "..."}  # optional agent-specific exports
# artifacts["report"] = { ... final structured JSON for frontend ... }

# internals["<agent>"] is entirely free-form and NOT a stable contract.
# runtime["<agent>"] defaults: {"status": "PENDING", "route": []}


# ---- Helpers ---------------------------------------------------------------

def default_agent_runtime() -> AgentRuntime:
    return {"status": "PENDING", "route": []}

def default_runtime_block() -> Runtime:
    return {
        "ia":   default_agent_runtime(),
        "idca": default_agent_runtime(),
        "naa":  default_agent_runtime(),
        "aa":   default_agent_runtime(),
    }

def frontend_view(state: GraphState) -> Dict[str, Any]:
    """
    Minimal frontend payload: only the final report + global status & ids.
    Use this in your /state/{id} handler if you want the UI to see report only.
    """
    artifacts = state.get("artifacts") or {}
    return {
        "request_id": state.get("request_id"),
        "status": state.get("status"),
        "created_at": state.get("created_at"),
        "updated_at": state.get("updated_at"),
        "report": artifacts.get("report") or {},   # ONLY expose final report
    }
