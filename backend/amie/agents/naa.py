# amie/agents/naa.py
# Novelty Assessment Agent (JSON-structured, IDCA-style LLM calling)
# Author: Harry
# 2025-09-12

import json
from typing import Dict, Any, List, Optional, Literal, Callable
from datetime import datetime, timezone

from google import genai  # noqa: F401
from google.genai import types  # noqa: F401
from langchain_core.runnables import RunnableLambda

from ..state import GraphState
from .schema.naa_schema import (
    SCHEMA_INVENTION_TYPE,
    SCHEMA_METHOD_DETAILS,
    SCHEMA_STRUCTURE_DETAILS,
    SCHEMA_CPC_L1_CODES,  # simplified schema: List[str]
)
from .prompt.naa_prompt import (
    build_prompt, build_prompt_sys,
    TPL_CPC_L1, format_innovation_taxonomy_text,  # noqa: F401 (taxonomy used later)
    SYS_PATENT_CLASSIFIER,
)

# ---------------------------------------------------------------------
# Literals (innovation type & source type)
# ---------------------------------------------------------------------
InnovationType = Literal[
    "process",      # Process / Method
    "machine",      # Machine
    "manufacture",  # Article of Manufacture
    "composition",  # Composition of Matter
    "design",       # Design (ornamental)
    "none",         # Not applicable / unclear
]

INNOVATION_TYPE_DESCRIPTIONS: Dict[InnovationType, str] = {
    "process": (
        "Process (Method): New algorithms, data-processing procedures, "
        "manufacturing or business processes, or new modes of human–computer interaction."
    ),
    "machine": "Machine: A specific hardware architecture, device, apparatus, or system.",
    "manufacture": (
        "Manufacture (Article of Manufacture): Newly created devices, tools, "
        "or manufactured articles/components."
    ),
    "composition": "Composition of Matter: New materials, chemical compounds, or formulations.",
    "design": "Design Patent (Ornamental Design): A new ornamental design or UI appearance.",
    "none": "None / Unclear: No identifiable patentable subject matter.",
}

# Reusable; may appear multiple times in later stages.
SourceType = Literal["arxiv", "google_patents", "uspto"]

MODEL_TEXT_DEFAULT = "gemini-2.0-flash-lite-001"


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d-%H-%M-%S")


def _empty_artifacts(message_note: str = "") -> Dict[str, Any]:
    return {
        "integrated": [],
        "detailed_checks": [],
        "invention_type": "none",
        "invention_details": {
            "method_steps": [],
            "structure_components": [],
            "notes": message_note or "no details (placeholder)",
        },
        "queries": [],
        "sources": [],
        "model_version": "naa-skel-0",
        "generated_at": _now_iso(),
        "input_summary": "",
        "cpc_level": {"level1": [], "level2": {}},
        "cpc_string": {"level1": "", "level2": {}},
    }


def _finish_with_message(msg: str) -> Dict[str, Any]:
    return {
        "artifacts": {"naa": _empty_artifacts()},
        "internals": {"naa": []},
        "runtime": {"naa": {"status": "FINISHED", "route": []}},
        "message": msg,
    }


def call_llm_json(
    *,
    client: "genai.Client",
    model: str,
    prompt_text: str,
    schema: Dict[str, Any],
) -> Any:
    """
    Text-only JSON call. Returns parsed JSON, or {} on error.
    """
    try:
        resp = client.models.generate_content(
            model=model,
            contents=[prompt_text],
            config=types.GenerateContentConfig(
                response_schema=schema,
                response_mime_type="application/json",
            ),
        )
        text = getattr(resp, "text", None)
        if not text:
            return {}
        return json.loads(text)
    except Exception:
        return {}


# ---------------------------------------------------------------------
# Sources pipeline (skeleton)
# ---------------------------------------------------------------------

SourceExec = Callable[[Dict[str, Any]], Dict[str, Any]]

def _exec_arxiv(ctx: Dict[str, Any]) -> Dict[str, Any]:
    # Placeholder: no network calls here. Define expected I/O shape only.
    return {"status": "SKIPPED", "reason": "not implemented", "format": "papers:list[dict]"}

def _exec_google_patents(ctx: Dict[str, Any]) -> Dict[str, Any]:
    return {"status": "SKIPPED", "reason": "not implemented", "format": "patents:list[dict]"}

def _exec_uspto(ctx: Dict[str, Any]) -> Dict[str, Any]:
    return {"status": "SKIPPED", "reason": "not implemented", "format": "patents:list[dict]"}

SOURCE_EXECUTORS: Dict[SourceType, SourceExec] = {
    "arxiv": _exec_arxiv,
    "google_patents": _exec_google_patents,
    "uspto": _exec_uspto,
}

def _get_sources_sequence(state: GraphState, cfg: Dict[str, Any]) -> List[SourceType]:
    """
    Determine the source sequence. Prefer state-provided ordered list, else fallback to config.
    """
    state_seq = (
        state.get("runtime", {}).get("sources")
        if isinstance(state.get("runtime"), dict) else None
    )
    if isinstance(state_seq, list) and all(isinstance(s, str) for s in state_seq):
        return state_seq  # type: ignore[return-value]
    cfg_seq = cfg.get("sources", [])
    return cfg_seq if isinstance(cfg_seq, list) else []

def _run_sources_pipeline(sources: List[SourceType], ctx: Dict[str, Any]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for s in sources:
        fn = SOURCE_EXECUTORS.get(s)  # may be None if unknown
        if fn is None:
            out.append({"source": s, "result": {"status": "SKIPPED", "reason": "no executor"}})
            continue
        out.append({"source": s, "result": fn(ctx)})
    return out


# ---------------------------------------------------------------------
# Main node
# ---------------------------------------------------------------------

def naa_node(state: GraphState, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    NAA node (step: CPC Level-1 classification with simple prompt),
    plus ordered sources pipeline scaffold (no-op).
    Input: summary (from IDCA), CPC strings from config.
    Output: artifacts.naa.cpc_level.level1 as List[str], and cpc_string from config.
    """
    try:
        # 0) Global precheck
        if state.get("status") == "FAILED":
            return _finish_with_message("NAA terminated because STATUS == FAILED.")

        # 1) IDCA completion precheck
        _idca_status = state["runtime"]["idca"]["status"]
        if _idca_status != "FINISHED":
            return _finish_with_message("NAA terminated due to IDCA terminated unexpected")

        # 2) Required inputs from state/config
        summary: str = state["artifacts"]["idca"]["summary"]
        cfg = (config or {}).get("configurable", {}) if isinstance(config, dict) else {}

        # -- EARLY: LLM client presence check (as requested) --
        client: Optional["genai.Client"] = cfg.get("genai_client")
        if client is None:
            return _finish_with_message("NAA terminated: LLM client missing.")

        model_name = cfg.get("model_name", MODEL_TEXT_DEFAULT)

        # CPC references (from config; do NOT recreate)
        cpc_strings = cfg.get("cpc_strings", {})    # {"level1": "A:...\nB:...\n...", "level2": {...}}
        cpc_level1_str = cpc_strings.get("level1", "") if isinstance(cpc_strings, dict) else ""

        # 3) Build prompt with shared system header (positional args only)
        #    Order: {0}=summary, {1}=level1 string
        prompt_text = build_prompt_sys(SYS_PATENT_CLASSIFIER, TPL_CPC_L1, summary, cpc_level1_str)

        # 4) Call LLM (schema: List[str] of CPC letters)
        level1_codes: List[str] = []
        result = call_llm_json(
            client=client,
            model=model_name,
            prompt_text=prompt_text,
            schema=SCHEMA_CPC_L1_CODES,
        )
        if isinstance(result, list) and all(isinstance(x, str) for x in result):
            level1_codes = result
        print("++++++++++++++++++++++++++++good++++++++++++++++++++++++++++")
        print()
        print()
        print()
        print(prompt_text)
        print()
        print()
        print()
        print(SCHEMA_CPC_L1_CODES)
        print()
        print()
        print()
        print(result)
        print()
        print()
        print()
        print("++++++++++++++++++++++++++++good++++++++++++++++++++++++++++")

        # 5) Placeholders for later steps
        invention_type: InnovationType = "none"
        invention_details: Dict[str, Any] = {
            "method_steps": [],
            "structure_components": [],
            "notes": "placeholder-only; no expansion performed",
        }

        # 6) Sources pipeline (ordered execution; skeleton only)
        sources_seq: List[SourceType] = _get_sources_sequence(state, cfg)
        pipeline_ctx: Dict[str, Any] = {
            "summary": summary,
            "cpc_level1_codes": level1_codes,
            "now": _now_iso(),
        }
        source_runs = _run_sources_pipeline(sources_seq, pipeline_ctx)

        # 7) Assemble artifacts
        naa_art: Dict[str, Any] = {
            "integrated": [],
            "detailed_checks": [],
            "invention_type": invention_type,
            "invention_details": invention_details,
            "queries": [],
            "sources": sources_seq,  # executed order
            "model_version": "naa-skel-4",
            "generated_at": _now_iso(),
            "input_summary": summary,
            "cpc_level": {
                "level1": level1_codes,
                "level2": {},            # not computed yet
            },
            "cpc_string": {
                "level1": cpc_level1_str,                 # newline-joined from config
                "level2": cpc_strings.get("level2", {}),  # pass-through from config
            },
        }

        naa_internals: List[Dict[str, Any]] = [
            {"stage": "precheck", "idca_status": _idca_status, "has_summary": bool(summary)},
            {"stage": "cpc_level1_classification", "template": TPL_CPC_L1, "result_len": len(level1_codes)},
            {"stage": "sources_pipeline", "sequence": sources_seq, "runs": source_runs},
            {
                "stage": "type_recognition",
                "note": "taxonomy available via format_innovation_taxonomy_text() for future prompts",
                "taxonomy_text": format_innovation_taxonomy_text(INNOVATION_TYPE_DESCRIPTIONS),
                "schema": SCHEMA_INVENTION_TYPE,
            },
            {
                "stage": "detail_expansion",
                "selected_schema": SCHEMA_METHOD_DETAILS if invention_type == "process" else SCHEMA_STRUCTURE_DETAILS,
            },
        ]

        return {
            "artifacts": {"naa": naa_art},
            "internals": {"naa": naa_internals},
            "runtime": {"naa": {"status": "FINISHED", "route": []}},
            "message": "naa finished CPC Level-1 classification (letters only) and executed sources scaffold",
        }

    except Exception as e:
        return _finish_with_message(f"NAA terminated due to error: {e!s}")


# ---------------------------------------------------------------------
# Dummy (kept for regression testing)
# ---------------------------------------------------------------------

def naa_node_dummy(state: GraphState, config=None) -> Dict[str, Any]:
    novelty_art = {
        "integrated": [],
        "detailed_checks": [],
        "invention_type": "process",
        "invention_details": {"method_steps": []},
        "queries": [{"q": "site:patents.google.com 3D printed robotic arm capstan drive", "why": "core features"}],
        "model_version": "naa-dummy-0",
        "generated_at": "yy-mm-dd-hh-mm-ss",
        "cpc_level": {"level1": [], "level2": {}},
        "cpc_string": {"level1": "", "level2": {}},
    }
    return {
        "runtime": {"naa": {"status": "FINISHED", "route": []}},
        "artifacts": {"naa": novelty_art},
        "internals": {"naa": []},
        "message": "naa mock finished",
    }


# Export as Runnable (kept; switch to naa_node when ready)
NOVELTY_A = RunnableLambda(naa_node)
