# amie/agents/naa.py
# Novelty Assessment Agent (JSON-structured, IDCA-style LLM calling)
# Author: Harry
# 2025-09-12

import json
import uuid
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
    SCHEMA_CPC_L1_CODES,
    SCHEMA_CPC_L2_DICT,
)
from .prompt.naa_prompt import (
    build_prompt_sys,
    TPL_CPC_L1, TPL_CPC_L2, TPL_INNOVATION_TYPE,
    TPL_DETAIL_METHOD, TPL_DETAIL_MACHINE, TPL_DETAIL_MANUFACTURE, TPL_DETAIL_COMPOSITION, TPL_DETAIL_DESIGN,
    format_innovation_taxonomy_text,
    SYS_PATENT_CLASSIFIER,
)

# ---------------------------------------------------------------------
# Literals
# ---------------------------------------------------------------------
InnovationType = Literal["process", "machine", "manufacture", "composition", "design", "none"]
SourceType = Literal["arxiv", "google_patents", "uspto"]

INNOVATION_TYPE_DESCRIPTIONS: Dict[InnovationType, str] = {
    "process": ("Process (Method): New algorithms, data-processing procedures, manufacturing or business "
                "processes, or new modes of human–computer interaction."),
    "machine": "Machine: A specific hardware architecture, device, apparatus, or system.",
    "manufacture": ("Manufacture (Article of Manufacture): Newly created devices, tools, or manufactured "
                    "articles/components."),
    "composition": "Composition of Matter: New materials, chemical compounds, or formulations.",
    "design": "Design Patent (Ornamental Design): A new ornamental design or UI appearance.",
    "none": "None / Unclear: No identifiable patentable subject matter.",
}

MODEL_TEXT_DEFAULT = "gemini-2.0-flash-lite-001"

# ---------------------------------------------------------------------
# Utils
# ---------------------------------------------------------------------
def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d-%H-%M-%S")

def _make_request_id() -> str:
    return str(uuid.uuid4())

def _log(req_id: str, tag: str, **kv: Any) -> None:
    """
    Single-line log used ONLY around LLM calls.
    Example: [NAA][CPC-L1][REQUEST] prompt="..." schema={...} | request_id=...
    """
    payload = " ".join(f"{k}={json.dumps(v, ensure_ascii=False)}" for k, v in kv.items())
    print(f"[NAA]{tag} {payload} | request_id={req_id}", flush=True)

def _detail_prompt_and_schema(itype: InnovationType) -> Tuple[str, Dict[str, Any]]:
    if itype == "process": return TPL_DETAIL_METHOD, SCHEMA_METHOD_DETAILS
    if itype == "machine": return TPL_DETAIL_MACHINE, SCHEMA_MACHINE_DETAILS
    if itype == "manufacture": return TPL_DETAIL_MANUFACTURE, SCHEMA_MANUFACTURE_DETAILS
    if itype == "composition": return TPL_DETAIL_COMPOSITION, SCHEMA_COMPOSITION_DETAILS
    if itype == "design": return TPL_DETAIL_DESIGN, SCHEMA_DESIGN_DETAILS
    return TPL_DETAIL_METHOD, SCHEMA_METHOD_DETAILS

# ---------------------------------------------------------------------
# LLM helpers (fail-fast; no internal logging)
# ---------------------------------------------------------------------
def call_llm_json(*, client: "genai.Client", model: str, prompt_text: str, schema: Dict[str, Any]) -> Any:
    resp = client.models.generate_content(
        model=model,
        contents=[prompt_text],
        config=types.GenerateContentConfig(response_schema=schema, response_mime_type="application/json"),
    )
    text = getattr(resp, "text", None)
    if not text:
        raise RuntimeError("LLM returned empty text")
    return json.loads(text)

def call_llm_json_with_pdf(
    *, client: "genai.Client", model: str, prompt_text: str, schema: Dict[str, Any],
    file_uri: Optional[str], mime_type: str = "application/pdf"
) -> Any:
    contents = []
    if file_uri:
        contents.append(types.Part.from_uri(file_uri=file_uri, mime_type=mime_type))
    contents.append(prompt_text)
    resp = client.models.generate_content(
        model=model,
        contents=contents,
        config=types.GenerateContentConfig(response_schema=schema, response_mime_type="application/json"),
    )
    text = getattr(resp, "text", None)
    if not text:
        raise RuntimeError("LLM returned empty text (pdf+instruction)")
    return json.loads(text)

# ---------------------------------------------------------------------
# Sources pipeline (skeleton; no logs)
# ---------------------------------------------------------------------
def _exec_arxiv(ctx: Dict[str, Any]) -> Dict[str, Any]:
    return {"status": "SKIPPED", "reason": "not implemented", "format": "papers:list[dict]"}

def _exec_google_patents(ctx: Dict[str, Any]) -> Dict[str, Any]:
    return {"status": "SKIPPED", "reason": "not implemented", "format": "patents:list[dict]"}

def _exec_uspto(ctx: Dict[str, Any]) -> Dict[str, Any]:
    return {"status": "SKIPPED", "reason": "not implemented", "format": "patents:list[dict]"}

SOURCE_EXECUTORS: Dict[SourceType, Callable[[Dict[str, Any]], Dict[str, Any]]] = {
    "arxiv": _exec_arxiv,
    "google_patents": _exec_google_patents,
    "uspto": _exec_uspto,
}

def _get_sources_sequence(state: GraphState, cfg: Dict[str, Any]) -> List[SourceType]:
    state_seq = state.get("runtime", {}).get("sources") if isinstance(state.get("runtime"), dict) else None
    if isinstance(state_seq, list) and all(isinstance(s, str) for s in state_seq):
        return state_seq  # type: ignore[return-value]
    cfg_seq = cfg.get("sources", [])
    return cfg_seq if isinstance(cfg_seq, list) else []

# ---------------------------------------------------------------------
# Main node (only LLM boundary logs)
# ---------------------------------------------------------------------
def naa_node(state: GraphState, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Steps:
      1) CPC Level-1
      2) CPC Level-2
      3) InnovationType
      4) Type-specific detail extraction (PDF-enabled)
      5) Sources scaffold
    Logging: ONLY two lines per LLM call (REQUEST / RESPONSE). Nothing else.
    """
    req_id = _make_request_id()
    cfg_root = (config or {})
    cfg = cfg_root.get("configurable", {}) if isinstance(cfg_root, dict) else {}

    # Inputs & prechecks (no logging here)
    if state.get("status") == "FAILED":
        raise RuntimeError("STATUS == FAILED")
    idca_status = state.get("runtime", {}).get("idca", {}).get("status", "?")
    if idca_status != "FINISHED":
        raise RuntimeError("IDCA not finished")

    summary: str = state.get("artifacts", {}).get("idca", {}).get("summary", "") or ""
    src_uri = state.get("artifacts", {}).get("idca", {}).get("doc_gcs_uri") or state.get("doc_gcs_uri")

    client: Optional["genai.Client"] = cfg.get("genai_client")
    if client is None:
        raise RuntimeError("LLM client missing")
    model_name = cfg.get("model_name", MODEL_TEXT_DEFAULT)

    cpc_strings = cfg.get("cpc_strings") or {}
    cpc_level1_str = cpc_strings.get("level1", "")
    cpc_level2_map_str = cpc_strings.get("level2", {})

    # (1) CPC L1
    prompt_l1 = build_prompt_sys(SYS_PATENT_CLASSIFIER, TPL_CPC_L1, summary, cpc_level1_str)
    _log(req_id, "[CPC-L1][REQUEST]", prompt=prompt_l1, schema=SCHEMA_CPC_L1_CODES)
    result_l1 = call_llm_json(client=client, model=model_name, prompt_text=prompt_l1, schema=SCHEMA_CPC_L1_CODES)
    level1_codes: List[str] = result_l1 if isinstance(result_l1, list) else []
    _log(req_id, "[CPC-L1][RESPONSE]", json=result_l1)

    # (2) CPC L2 (only if options exist)
    level2_parts: List[str] = []
    for sec in level1_codes:
        block = cpc_level2_map_str.get(sec)
        if block:
            level2_parts.append(f"### {sec}\n{block}")
    level2_options_str = "\n\n".join(level2_parts)

    level2_dict: Dict[str, str] = {}
    if level2_options_str.strip():
        prompt_l2 = build_prompt_sys(SYS_PATENT_CLASSIFIER, TPL_CPC_L2, summary, level2_options_str)
        _log(req_id, "[CPC-L2][REQUEST]", prompt=prompt_l2, schema=SCHEMA_CPC_L2_DICT)
        result_l2 = call_llm_json(client=client, model=model_name, prompt_text=prompt_l2, schema=SCHEMA_CPC_L2_DICT)
        if not isinstance(result_l2, dict):
            raise RuntimeError("CPC-L2: LLM response is not a dict")
        level2_dict = result_l2
        _log(req_id, "[CPC-L2][RESPONSE]", json=result_l2)

    # (3) InnovationType
    taxonomy_text = format_innovation_taxonomy_text(INNOVATION_TYPE_DESCRIPTIONS)
    level2_str = "\n".join(f"{k}: {v}" for k, v in level2_dict.items()) if level2_dict else ""
    extended_summary = summary if not level2_str else f"{summary}\n\n[CPC Level-2 selections]\n{level2_str}"
    prompt_innov = build_prompt_sys(SYS_PATENT_CLASSIFIER, TPL_INNOVATION_TYPE, extended_summary, taxonomy_text)
    _log(req_id, "[TYPE][REQUEST]", prompt=prompt_innov, schema=SCHEMA_INVENTION_TYPE)
    result_innov = call_llm_json(client=client, model=model_name, prompt_text=prompt_innov, schema=SCHEMA_INVENTION_TYPE)
    if not isinstance(result_innov, dict) or "invention_type" not in result_innov:
        raise RuntimeError("InnovationType: invalid JSON")
    invention_type: InnovationType = result_innov["invention_type"].strip().lower()  # type: ignore[assignment]
    _log(req_id, "[TYPE][RESPONSE]", json=result_innov)

    if invention_type == "none":
        raise RuntimeError("InnovationType is 'none'")

    # (4) Detail extraction
    prompt_key, schema_obj = _detail_prompt_and_schema(invention_type)
    type_desc = INNOVATION_TYPE_DESCRIPTIONS[invention_type]  # type: ignore[index]
    prompt_detail = build_prompt_sys(SYS_PATENT_CLASSIFIER, prompt_key, summary, invention_type, type_desc, str(src_uri or ""))
    _log(req_id, "[DETAIL][REQUEST]", prompt=prompt_detail, schema=schema_obj, uri=src_uri)
    details_json = call_llm_json_with_pdf(
        client=client, model=model_name, prompt_text=prompt_detail, schema=schema_obj, file_uri=src_uri
    )
    if not isinstance(details_json, dict):
        raise RuntimeError("Detail extraction: invalid JSON")
    _log(req_id, "[DETAIL][RESPONSE]", json=details_json)

    # (5) Sources scaffold (no logging by request)
    sources_seq: List[SourceType] = _get_sources_sequence(state, cfg)
    source_runs = []
    for s in sources_seq:
        exec_fn = SOURCE_EXECUTORS.get(s)
        res = {"status": "SKIPPED", "reason": "no executor"} if exec_fn is None else exec_fn({
            "summary": summary,
            "cpc_level1_codes": level1_codes,
            "cpc_level2_dict": level2_dict,
            "invention_type": invention_type,
            "now": _now_iso(),
        })
        source_runs.append({"source": s, "result": res})

    # Assemble artifacts
    naa_art: Dict[str, Any] = {
        "integrated": [],
        "detailed_checks": [],
        "invention_type": invention_type,
        "invention_details": details_json,
        "queries": [],
        "sources": sources_seq,
        "model_version": "naa-skel-10",
        "generated_at": _now_iso(),
        "input_summary": summary,
        "cpc_level": {"level1": level1_codes, "level2": level2_dict},
        "cpc_string": {"level1": cpc_level1_str, "level2": cpc_level2_map_str},
        "doc_gcs_uri": src_uri or "",
    }

    return {
        "artifacts": {"naa": naa_art},
        "internals": {"naa": [
            {"stage": "cpc_level1_classification", "codes": level1_codes},
            {"stage": "cpc_level2_classification", "dict": level2_dict},
            {"stage": "innovation_type_classification", "result": result_innov},
            {"stage": "detail_extraction", "schema_keys": list(schema_obj.get("properties", {}).keys())},
            {"stage": "sources_pipeline", "runs": source_runs},
        ]},
        "runtime": {"naa": {"status": "FINISHED", "route": []}},
        "message": "NAA completed",
    }

# Export as Runnable
NOVELTY_A = RunnableLambda(naa_node)
