# amie/agents/aggregation_agent.py
# Aggregation Agent
# Author: Harry
# 2025-08-18

import json
from typing import Dict, Any
from datetime import datetime, timezone

from langchain_core.runnables import RunnableLambda
from ..state import GraphState


# -------------------------------
# COMPLETE VERSION (default-exported aa_node)
# -------------------------------
def _default_ingestion() -> Dict[str, Any]:
    return {
        "ok": None,
        "doc_uri": None,
        "storage": None,
        "bucket": None,
        "object": None,
        "size": None,
        "content_type": None,
        "updated_iso": None,
        "doc_local_uri": None,
        "is_pdf": None,
    }

def _default_idca() -> Dict[str, Any]:
    return {
        "status": "unknown",
        "summary": "",
        "fields": [],
        "reasoning": "",
        "model_version": None,
    }

def _default_novelty() -> Dict[str, Any]:
    return {
        "scores": {
            "novelty": None,
            "significance": None,
            "rigor": None,
            "clarity": None,
        },
        "highlights": [],
        "risks": [],
        "summary": "",
        "reasoning": "",
        "model_version": None,
    }

def _safe_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(base)
    for k, v in (override or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            inner = dict(out[k])
            for ik, iv in v.items():
                if iv is not None:
                    inner[ik] = iv
            out[k] = inner
        else:
            if v is not None:
                out[k] = v
    return out

def _timestamp_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def aa_node(state: GraphState) -> Dict[str, Any]:
    """
    Aggregation Agent (complete, default):
    - Ensures ingestion/idca/novelty sections always exist with defaults.
    - Does not perform any decision logic, verdict fixed "UNDECIDED".
    """
    request_id = state.get("request_id")
    artifacts = state.get("artifacts") or {}
    ia_in = artifacts.get("ia") or {}
    idca_in = artifacts.get("idca") or {}
    naa_in = artifacts.get("naa") or {}

    ia = _safe_merge(_default_ingestion(), ia_in)
    idca = _safe_merge(_default_idca(), idca_in)
    naa = _safe_merge(_default_novelty(), naa_in)

    report = {
        "meta": {
            "request_id": request_id,
            "generated_at": _timestamp_utc_iso(),
            "schema_version": "aa-report-v1",
        },
        "ia": ia,
        "idca": idca,
        "naa": naa,
        "verdict": "UNDECIDED",
    }

    aa_cache = {
        "mode": "structure-completion-only",
        "merge_policy": "shallow-default-fill",
        "inputs_present": {
            "ingestion": bool(ia_in),
            "idca": bool(idca_in),
            "novelty": bool(naa_in),
        },
    }
    print("\n")
    print("="*31, "END","="*31)
    return {
        "artifacts": {
            "report": report,
            "ia": ia,
            "idca": idca,
            "naa": naa,
        },
        "internals": {"aa": aa_cache},
        "runtime": {"aa": {"status": "FINISHED", "route": []}},
        "logs": [f"AA: complete structure aggregation done. request_id={request_id}"],
    }


# -------------------------------
# DUMMY VERSION (kept for testing)
# -------------------------------
def aa_node_dummy(state: GraphState) -> Dict[str, Any]:
    """
    Aggregation Agent (dummy):
    - Just stitches together artifacts without filling missing parts.
    - Verdict is fixed "UNDECIDED (dummy)".
    """
    arts = state.get("artifacts") or {}
    idca = arts.get("idca") or {}
    novelty = arts.get("novelty") or {}
    ingestion = arts.get("ingestion") or {}

    report = {
        "ingestion": ingestion,
        "idca": idca,
        "novelty": novelty,
        "verdict": "UNDECIDED (dummy)",
    }
    aa_cache = {
        "weights": {"idca": 0.5, "naa": 0.5},
        "merge_policy": "dummy-avg",
    }

    return {
        "artifacts": {"report": report},
        "internals": {"aa": aa_cache},
        "logs": ["AA: dummy aggregation complete."],
    }


# -------------------------------
# Export
# -------------------------------
AGGREGATION = RunnableLambda(aa_node)
