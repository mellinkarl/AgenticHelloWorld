# amie/agents/naa.py
# Novelty Assessment Agent (JSON-structured, IDCA-style LLM calling)
# Author: Harry
# 2025-09-12

import json
from typing import Dict, Any, List, Optional, Literal, Callable, Tuple
from datetime import datetime, timezone

from google import genai  # noqa: F401
from google.genai import types  # noqa: F401
from langchain_core.runnables import RunnableLambda

from ..state import GraphState
from .schema.naa_schema import (
    SCHEMA_INVENTION_TYPE,
    SCHEMA_METHOD_DETAILS,
    SCHEMA_MACHINE_DETAILS,
    SCHEMA_MANUFACTURE_DETAILS,
    SCHEMA_COMPOSITION_DETAILS,
    SCHEMA_DESIGN_DETAILS,
    SCHEMA_CPC_L1_CODES,   # List[str]
    SCHEMA_CPC_L2_DICT,    # Dict[str, str]
)
from .prompt.naa_prompt import (
    build_prompt_sys,
    TPL_CPC_L1, TPL_CPC_L2, TPL_INNOVATION_TYPE,
    TPL_DETAIL_METHOD, TPL_DETAIL_MACHINE, TPL_DETAIL_MANUFACTURE, TPL_DETAIL_COMPOSITION, TPL_DETAIL_DESIGN,
    format_innovation_taxonomy_text,
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


def call_llm_json_with_pdf(
    *,
    client: "genai.Client",
    model: str,
    prompt_text: str,
    schema: Dict[str, Any],
    file_uri: Optional[str],
    mime_type: str = "application/pdf",
) -> Any:
    """
    PDF + instruction JSON call. Returns parsed JSON, or {} on error.
    If file_uri is falsy, falls back to text-only call.
    """
    try:
        contents = []
        if file_uri:
            contents.append(types.Part.from_uri(file_uri=file_uri, mime_type=mime_type))
        contents.append(prompt_text)
        resp = client.models.generate_content(
            model=model,
            contents=contents,
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
# Detail extraction routing
# ---------------------------------------------------------------------

def _detail_prompt_and_schema(itype: InnovationType) -> Tuple[str, Dict[str, Any]]:
    if itype == "process":
        return TPL_DETAIL_METHOD, SCHEMA_METHOD_DETAILS
    if itype == "machine":
        return TPL_DETAIL_MACHINE, SCHEMA_MACHINE_DETAILS
    if itype == "manufacture":
        return TPL_DETAIL_MANUFACTURE, SCHEMA_MANUFACTURE_DETAILS
    if itype == "composition":
        return TPL_DETAIL_COMPOSITION, SCHEMA_COMPOSITION_DETAILS
    if itype == "design":
        return TPL_DETAIL_DESIGN, SCHEMA_DESIGN_DETAILS
    # Fallback
    return TPL_DETAIL_METHOD, SCHEMA_METHOD_DETAILS


# ---------------------------------------------------------------------
# Main node
# ---------------------------------------------------------------------

def naa_node(state: GraphState, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    NAA node:
      1) CPC Level-1 classification (letters) via LLM.
      2) CPC Level-2 classification (dict{class_code:title}) via LLM using Level-1 sections.
      3) InnovationType classification via LLM using (summary + Level-2 string + taxonomy descriptions).
      4) Detail extraction via LLM using (doc_gcs_uri + summary + InnovationType + description).
      5) Sources pipeline scaffold (no-op).
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
        # doc URI can be stored in different places depending on previous pipeline stages
        src_uri = (
            state.get("artifacts", {}).get("idca", {}).get("doc_gcs_uri")
            or state.get("doc_gcs_uri")
            or state.get("doc_gcs_url")  # alternative key spelling
        )
        cfg = (config or {}).get("configurable", {}) if isinstance(config, dict) else {}

        # -- EARLY: LLM client presence check --
        client: Optional["genai.Client"] = cfg.get("genai_client")
        if client is None:
            return _finish_with_message("NAA terminated: LLM client missing.")
        model_name = cfg.get("model_name", MODEL_TEXT_DEFAULT)

        # CPC references (from config; guaranteed present)
        cpc_strings = cfg.get("cpc_strings")             # {"level1": "...", "level2": { "A": "...", ... }}
        cpc_level1_str = cpc_strings.get("level1")
        cpc_level2_map_str = cpc_strings.get("level2")   # dict: section -> newline-joined classes string

        # 3) Level-1 prompt & call
        prompt_l1 = build_prompt_sys(SYS_PATENT_CLASSIFIER, TPL_CPC_L1, summary, cpc_level1_str)
        level1_codes: List[str] = []
        result_l1 = call_llm_json(
            client=client,
            model=model_name,
            prompt_text=prompt_l1,
            schema=SCHEMA_CPC_L1_CODES,
        )
        if isinstance(result_l1, list) and all(isinstance(x, str) for x in result_l1):
            level1_codes = result_l1

        # 4) Level-2 options assembly (only for chosen Level-1 sections)
        level2_options_str_parts: List[str] = []
        for sec in level1_codes:
            sec_block = cpc_level2_map_str.get(sec)
            if sec_block:
                level2_options_str_parts.append(f"### {sec}\n{sec_block}")
        level2_options_str = "\n\n".join(level2_options_str_parts)

        # 5) Level-2 prompt & call (if we have options)
        level2_dict: Dict[str, str] = {}
        assert level2_options_str.strip(), "No CPC Level-2 options available for the selected Level-1 sections."
        prompt_l2 = build_prompt_sys(SYS_PATENT_CLASSIFIER, TPL_CPC_L2, summary, level2_options_str)

        result_l2 = call_llm_json(
            client=client,
            model=model_name,
            prompt_text=prompt_l2,
            schema=SCHEMA_CPC_L2_DICT,
        )

        if isinstance(result_l2, dict) and all(isinstance(k, str) and isinstance(v, str) for k, v in result_l2.items()):
            level2_dict = result_l2

        # 6) InnovationType classification
        level2_str = "\n".join(f"{k}: {v}" for k, v in level2_dict.items()) if level2_dict else ""
        taxonomy_text = format_innovation_taxonomy_text(INNOVATION_TYPE_DESCRIPTIONS)
        extended_summary = summary if not level2_str else f"{summary}\n\n[CPC Level-2 selections]\n{level2_str}"

        prompt_innov = build_prompt_sys(
            SYS_PATENT_CLASSIFIER,
            TPL_INNOVATION_TYPE,
            extended_summary,
            taxonomy_text,
        )
        result_innov = call_llm_json(
            client=client,
            model=model_name,
            prompt_text=prompt_innov,
            schema=SCHEMA_INVENTION_TYPE,
        )

        invention_type: InnovationType = "none"
        if isinstance(result_innov, dict) and isinstance(result_innov.get("invention_type"), str):
            candidate = result_innov["invention_type"].strip().lower()
            if candidate in {"process", "machine", "manufacture", "composition", "design", "none"}:
                invention_type = candidate  # type: ignore[assignment]

        # 7) Detail extraction for the selected InnovationType (if any)
        invention_details: Dict[str, Any] = {"notes": "no details (skipped)"}
        detail_internals: Dict[str, Any] = {"attempted": False, "prompt_key": None, "schema_keys": []}

        assert invention_type != "none", "invention_type == none, IDCA should mark implied"
        prompt_key, schema_obj = _detail_prompt_and_schema(invention_type)
        type_desc = INNOVATION_TYPE_DESCRIPTIONS[invention_type]
        prompt_detail = build_prompt_sys(
            SYS_PATENT_CLASSIFIER,
            prompt_key,
            summary,                 # {0}
            invention_type,          # {1}
            type_desc,               # {2}
            str(src_uri or ""),      # {3}
        )
        details_json = call_llm_json_with_pdf(
            client=client,
            model=model_name,
            prompt_text=prompt_detail,
            schema=schema_obj,
            file_uri=src_uri,
        )
        if isinstance(details_json, dict):
            invention_details = details_json
        else:
            invention_details = {"notes": "unclear"}

        detail_internals = {
            "attempted": True,
            "prompt_key": prompt_key,
            "schema_keys": list(schema_obj.get("properties", {}).keys()),
            "has_pdf": bool(src_uri),
            "result_nonempty": bool(invention_details),
        }
        print()
        print()
        print()
        print()
        print()
        print(details_json)
        print()
        print()
        print()
        print()
        # 8) Sources pipeline (ordered execution; skeleton only)
        sources_seq: List[SourceType] = _get_sources_sequence(state, cfg)
        pipeline_ctx: Dict[str, Any] = {
            "summary": summary,
            "cpc_level1_codes": level1_codes,
            "cpc_level2_dict": level2_dict,
            "invention_type": invention_type,
            "now": _now_iso(),
        }
        source_runs = _run_sources_pipeline(sources_seq, pipeline_ctx)

        # 9) Assemble artifacts
        naa_art: Dict[str, Any] = {
            "integrated": [],
            "detailed_checks": [],
            "invention_type": invention_type,
            "invention_details": invention_details,
            "queries": [],
            "sources": sources_seq,  # executed order
            "model_version": "naa-skel-7",
            "generated_at": _now_iso(),
            "input_summary": summary,
            "cpc_level": {
                "level1": level1_codes,   # List[str]
                "level2": level2_dict,    # Dict[str,str] chosen by LLM
            },
            "cpc_string": {
                "level1": cpc_level1_str,     # newline-joined from config
                "level2": cpc_level2_map_str, # dict section->newline-joined classes string (from config)
            },
            "doc_gcs_uri": src_uri or "",
        }

        naa_internals: List[Dict[str, Any]] = [
            {"stage": "precheck", "idca_status": _idca_status, "has_summary": bool(summary)},
            {"stage": "cpc_level1_classification", "template": TPL_CPC_L1, "result_len": len(level1_codes)},
            {
                "stage": "cpc_level2_classification",
                "template": TPL_CPC_L2,
                "sections": level1_codes,
                "options_len": len(level2_options_str_parts),
                "result_len": len(level2_dict),
            },
            {
                "stage": "innovation_type_classification",
                "template": TPL_INNOVATION_TYPE,
                "taxonomy_text": taxonomy_text,
                "level2_str_len": len(level2_str),
                "result": result_innov if isinstance(result_innov, dict) else {},
                "selected_innovation_type": invention_type,
            },
            {
                "stage": "detail_extraction",
                "info": detail_internals,
            },
            {"stage": "sources_pipeline", "sequence": sources_seq, "runs": source_runs},
        ]

        return {
            "artifacts": {"naa": naa_art},
            "internals": {"naa": naa_internals},
            "runtime": {"naa": {"status": "FINISHED", "route": []}},
            "message": "naa finished CPC L1/L2, InnovationType, and type-specific detail extraction; sources scaffold executed",
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


# Export as Runnable (wire to real node)
NOVELTY_A = RunnableLambda(naa_node)
