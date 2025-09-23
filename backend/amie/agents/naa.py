# amie/agents/naa.py
# Novelty Assessment Agent (API-based Scholar search + direct PDF-to-PDF LLM compare)
# Author: Harry
# 2025-09-23

import json
from typing import Dict, Any, List, Optional, Literal, Tuple
from datetime import datetime, timezone
import time
import re

try:
    import requests  # 可选，仅用于 HEAD 检测（本版仅打印，不做强过滤）
except Exception:
    requests = None  # guard at runtime

# >>> 新增：scholarly 作为 Google Scholar 后端
try:
    from scholarly import scholarly as _scholarly  # type: ignore
except Exception:
    _scholarly = None  # 运行时缺失则 graceful 退出

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
    SCHEMA_NOVELTY_ASPECTS,
    SCHEMA_SCHOLAR_SINGLE_QUERY,
    SCHEMA_COMPARE_RESULT,
)
from .prompt.naa_prompt import (
    build_prompt_sys,
    TPL_CPC_L1, TPL_CPC_L2, TPL_INNOVATION_TYPE,
    TPL_DETAIL_METHOD, TPL_DETAIL_MACHINE, TPL_DETAIL_MANUFACTURE, TPL_DETAIL_COMPOSITION, TPL_DETAIL_DESIGN,
    TPL_NOVELTY_ASPECTS,
    TPL_SCHOLAR_SINGLE_QUERY,
    TPL_COMPARE_PDFS,
    format_innovation_taxonomy_text,
    SYS_PATENT_CLASSIFIER,
)

# ---------------------------------------------------------------------
# Literals
# ---------------------------------------------------------------------
InnovationType = Literal["process", "machine", "manufacture", "composition", "design", "none"]
SourceType = Literal["google_scholar_scholarly"]  # 使用 scholarly

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
# Simple helpers
# ---------------------------------------------------------------------
def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d-%H-%M-%S")


def _finish_with_message(msg: str) -> Dict[str, Any]:
    """Uniform early-finish payload."""
    return {
        "artifacts": {"naa": {
            "integrated": [],
            "detailed_checks": [],
            "invention_type": "none",
            "invention_details": {},
            "sources": [],
            "model_version": "naa-scholar-v1",
            "generated_at": _now_iso(),
            "input_summary": "",
            "cpc_level": {"level1": [], "level2": {}},
            "doc_gcs_uri": "",
            "novelty_aspects": [],
            "search_query": "",
            "reference_pdfs": [],
        }},
        "internals": {"naa": []},
        "runtime": {"naa": {"status": "FINISHED", "route": []}},
        "message": msg,
    }


def _detail_prompt_and_schema(itype: InnovationType) -> Tuple[str, Dict[str, Any]]:
    if itype == "process": return TPL_DETAIL_METHOD, SCHEMA_METHOD_DETAILS
    if itype == "machine": return TPL_DETAIL_MACHINE, SCHEMA_MACHINE_DETAILS
    if itype == "manufacture": return TPL_DETAIL_MANUFACTURE, SCHEMA_MANUFACTURE_DETAILS
    if itype == "composition": return TPL_DETAIL_COMPOSITION, SCHEMA_COMPOSITION_DETAILS
    if itype == "design": return TPL_DETAIL_DESIGN, SCHEMA_DESIGN_DETAILS
    return TPL_DETAIL_METHOD, SCHEMA_METHOD_DETAILS

# ---------------------------------------------------------------------
# Pretty LLM I/O logging — ONLY prints LLM inputs & outputs
# ---------------------------------------------------------------------
def _print_llm_input(tag: str, *, prompt: str, schema: Optional[Dict[str, Any]] = None, pdf_attached: bool = False) -> None:
    print("\n" + "=" * 76)
    print(f"LLM INPUT [{tag}]")
    print("-" * 76)
    print(f"PDF attached: {pdf_attached}")
    if schema is not None:
        try:
            print("Schema:")
            print(json.dumps(schema, ensure_ascii=False, indent=2, sort_keys=True))
        except Exception:
            print("Schema: <unprintable>")
    print("\nPrompt:\n")
    print(prompt)
    print("=" * 76, flush=True)


def _print_llm_output(tag: str, *, text: Optional[str] = None, obj: Optional[Any] = None) -> None:
    print("\n" + "-" * 76)
    print(f"LLM OUTPUT [{tag}]")
    print("-" * 76)
    if obj is not None:
        try:
            print(json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True))
        except Exception:
            print("<non-JSON object>")
    elif text is not None:
        print(text)
    else:
        print("<empty>")
    print("-" * 76 + "\n", flush=True)

# ---------------------------------------------------------------------
# LLM wrappers
# ---------------------------------------------------------------------
def call_llm_json(*, client: "genai.Client", model: str, tag: str, prompt_text: str, schema: Dict[str, Any]) -> Any:
    _print_llm_input(tag, prompt=prompt_text, schema=schema, pdf_attached=False)
    resp = client.models.generate_content(
        model=model,
        contents=[prompt_text],
        config=types.GenerateContentConfig(response_schema=schema, response_mime_type="application/json"),
    )
    text = getattr(resp, "text", "") or ""
    try:
        data = json.loads(text)
        _print_llm_output(tag, obj=data)
        return data
    except Exception:
        _print_llm_output(tag, text=text)
        raise RuntimeError(f"{tag}: LLM returned non-JSON text")


def call_llm_json_with_pdf(
    *, client: "genai.Client", model: str, tag: str, prompt_text: str, schema: Dict[str, Any],
    file_uri: Optional[str], mime_type: str = "application/pdf"
) -> Any:
    contents = []
    pdf_attached = bool(file_uri)
    if file_uri:
        contents.append(types.Part.from_uri(file_uri=file_uri, mime_type=mime_type))
    contents.append(prompt_text)
    _print_llm_input(tag, prompt=prompt_text, schema=schema, pdf_attached=pdf_attached)
    resp = client.models.generate_content(
        model=model,
        contents=contents,
        config=types.GenerateContentConfig(response_schema=schema, response_mime_type="application/json"),
    )
    text = getattr(resp, "text", "") or ""
    try:
        data = json.loads(text)
        _print_llm_output(tag, obj=data)
        return data
    except Exception:
        _print_llm_output(tag, text=text)
        raise RuntimeError(f"{tag}: LLM returned non-JSON text")

# ---------------------------------------------------------------------
# Scholar (scholarly) — 仅 arXiv，尽量拿到 PDF 直链，并打印每一步
# ---------------------------------------------------------------------
def _arxiv_abs_to_pdf(url: str) -> str:
    """Convert https://arxiv.org/abs/<id> -> https://arxiv.org/pdf/<id>.pdf"""
    if not url:
        return ""
    m = re.search(r"https?://arxiv\.org/abs/([^\s?#]+)", url, re.IGNORECASE)
    return f"https://arxiv.org/pdf/{m.group(1)}.pdf" if m else ""


def _looks_like_arxiv(url: str) -> bool:
    return bool(url) and ("arxiv.org" in url.lower())


def _search_google_scholar_serpapi_arxiv_pdfs(query: str, *, serpapi_key: str, limit: int) -> List[Dict[str, Any]]:
    """
    NOTE: Signature kept for compatibility; 'serpapi_key' is ignored.
    Implementation uses `scholarly` to query Google Scholar.

    Returns a list of dicts:
      { "title": str, "abs_url": str, "pdf_url": str, "year": str, "source": "arxiv" }

    Printing:
      - Before iterating, prints the raw query.
      - For each candidate, prints title/pub_url/eprint_url.
      - Prints computed pdf_url (or <none>) attempt result.
      - After collection, prints how many arXiv PDFs were found.
    """
    print("\n" + "=" * 76)
    print("[scholarly] START SCHOLAR QUERY")
    print("query:", query)
    print("=" * 76)

    out: List[Dict[str, Any]] = []

    if not query:
        print("[scholarly] empty query — return []")
        return out

    if _scholarly is None:
        print("[scholarly] library unavailable — return []")
        return out

    try:
        # search_pubs returns an iterator of publication dicts (lightweight).
        # We'll iteratively fill each item to obtain more fields (e.g., eprint_url).
        search_iter = _scholarly.search_pubs(query)  # type: ignore
    except Exception as e:
        print(f"[scholarly] search_pubs failed: {e!r}")
        return out

    collected = 0
    # We don't know how many are arXiv; so we iterate more than 'limit' candidates,
    # but only keep arXiv entries until we reach 'limit'.
    hard_cap = max(limit * 3, limit)  # scan window
    idx = 0

    while collected < limit and idx < hard_cap:
        idx += 1
        try:
            pub = next(search_iter)
        except StopIteration:
            break
        except Exception as e:
            print(f"[scholarly] iterator error: {e!r}")
            break

        # Basic fields from lightweight pub
        title = ""
        pub_url = ""
        year = ""
        eprint_url = ""

        try:
            # Fill to get detailed fields (bib / pub_url / eprint_url ...)
            pub_filled = _scholarly.fill(pub)  # type: ignore
        except Exception as e:
            print(f"[scholarly] fill failed: {e!r}")
            pub_filled = pub

        bib = pub_filled.get("bib", {}) if isinstance(pub_filled, dict) else {}
        title = (bib.get("title") or pub_filled.get("title") or "").strip()
        pub_url = (pub_filled.get("pub_url") or "").strip()
        eprint_url = (pub_filled.get("eprint_url") or "").strip()
        year_val = (bib.get("pub_year") or bib.get("year") or pub_filled.get("year") or "")
        year = str(year_val).strip() if year_val else ""

        print("-" * 76)
        print(f"[scholarly] cand: {title or '<no title>'}")
        print(f"  pub_url   = {pub_url or '<none>'}")
        print(f"  eprint_url= {eprint_url or '<none>'}")

        # Keep only arXiv
        if not (_looks_like_arxiv(pub_url) or _looks_like_arxiv(eprint_url)):
            print("  -> skip: not arXiv")
            continue

        # Compute a plausible PDF url
        pdf_url = ""
        # 1) If eprint_url is already a PDF
        if eprint_url.lower().endswith(".pdf"):
            pdf_url = eprint_url
        # 2) If eprint_url is an abs page
        if (not pdf_url) and _looks_like_arxiv(eprint_url):
            pdf_url = _arxiv_abs_to_pdf(eprint_url)
        # 3) Fallback to pub_url
        if (not pdf_url) and pub_url.lower().endswith(".pdf") and _looks_like_arxiv(pub_url):
            pdf_url = pub_url
        if (not pdf_url) and _looks_like_arxiv(pub_url):
            pdf_url = _arxiv_abs_to_pdf(pub_url)

        print(f"  pdf_url?  = {pdf_url or '<none>'}")

        # 仅打印，不强制 HEAD 过滤（避免误杀）
        if requests and pdf_url:
            try:
                h = requests.head(pdf_url, allow_redirects=True, timeout=8)
                print(f"  HEAD status={h.status_code} content-type={h.headers.get('Content-Type','')}")
            except Exception as he:
                print(f"  HEAD error: {he!r}")

        if not pdf_url:
            print("  -> skip: no PDF url derivable")
            continue

        out.append({
            "title": title,
            "abs_url": pub_url if _looks_like_arxiv(pub_url) else (eprint_url or pub_url),
            "pdf_url": pdf_url,
            "year": year,
            "source": "arxiv",
        })
        collected += 1

    print("=" * 76)
    print(f"[scholarly] DONE — arXiv PDFs collected: {len(out)} (limit={limit}, scanned≈{idx})")
    print("=" * 76 + "\n")
    return out

# ---------------------------------------------------------------------
# PDF-vs-PDF comparison (LLM). No metadata; use PDFs ONLY.
# ---------------------------------------------------------------------
def _compare_pdfs_with_invention(
    *, client: "genai.Client", model: str,
    invention_pdf_uri: str,
    candidate_pdf_url: str
) -> Dict[str, Any]:
    """
    Feed two PDFs at once. If either is missing -> caller should skip before calling.
    """
    prompt = TPL_COMPARE_PDFS  # includes strict JSON shape
    parts = [
        types.Part.from_uri(file_uri=invention_pdf_uri, mime_type="application/pdf"),
        types.Part.from_uri(file_uri=candidate_pdf_url, mime_type="application/pdf"),
        prompt,
    ]
    _print_llm_input("COMPARE-PDFS", prompt=prompt, schema=SCHEMA_COMPARE_RESULT, pdf_attached=True)
    resp = client.models.generate_content(
        model=model,
        contents=parts,
        config=types.GenerateContentConfig(
            response_schema=SCHEMA_COMPARE_RESULT,
            response_mime_type="application/json"
        ),
    )
    text = getattr(resp, "text", "") or ""
    try:
        data = json.loads(text)
        _print_llm_output("COMPARE-PDFS", obj=data)
        data["similarity"] = float(data.get("similarity", 0.0))
        data["overlap"] = [s for s in data.get("overlap", []) if isinstance(s, str)]
        data["novelty"] = [s for s in data.get("novelty", []) if isinstance(s, str)]
        return data
    except Exception:
        _print_llm_output("COMPARE-PDFS", text=text)
        return {"overlap": [], "novelty": [], "similarity": 0.0}

# ---------------------------------------------------------------------
# Main node
# ---------------------------------------------------------------------
def naa_node(state: GraphState, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Flow:
      0) Prechecks (state.status, IDCA finished)
      1) CPC Level-1 (LLM)
      2) CPC Level-2 (LLM)
      3) InnovationType (LLM)
      4) Detail extraction (LLM + optional PDF for invention)
      5) Enumerate ALL novelty aspects (LLM)
      6) Generate ONE Google Scholar query (LLM) — targeting arXiv domain
      7) Call scholarly → collect arXiv PDF links (prints details)
      8) Print full reference PDF list (capped by `reference_max`)
      9) For each PDF: compare (PDF+PDF to LLM)
      10) Sort by similarity desc and return
    """
    # --- prechecks ---
    if state.get("status") == "FAILED":
        return _finish_with_message("NAA terminated because a previous stage failed.")
    idca_status = state.get("runtime", {}).get("idca", {}).get("status")
    if idca_status != "FINISHED":
        return _finish_with_message("NAA terminated due to upstream not finished (IDCA).")

    # --- inputs ---
    summary: str = state.get("artifacts", {}).get("idca", {}).get("summary", "") or ""
    invention_pdf_uri = state.get("artifacts", {}).get("idca", {}).get("doc_gcs_uri") or state.get("doc_gcs_uri") or ""
    if not invention_pdf_uri:
        return _finish_with_message("NAA terminated: invention PDF URI missing.")

    cfg_root = (config or {})
    cfg = cfg_root.get("configurable", {}) if isinstance(cfg_root, dict) else {}
    client: Optional["genai.Client"] = cfg.get("genai_client")
    if client is None:
        return _finish_with_message("NAA terminated because LLM client is missing.")
    model_name = cfg.get("model_name", MODEL_TEXT_DEFAULT)
    cpc_strings = cfg.get("cpc_strings") or {}
    cpc_level1_str = cpc_strings.get("level1", "")
    cpc_level2_map_str = cpc_strings.get("level2", {})

    # scholar search config (scholarly 不需要 key)
    search_backend: SourceType = "google_scholar_scholarly"
    per_page_k: int = int(cfg.get("per_page_k", 20))            # 仅作为上限窗口
    reference_max: int = int(cfg.get("reference_max", 10))      # cap the PDF list
    compare_delay: float = float(cfg.get("compare_delay_s", 0.0))

    if _scholarly is None:
        return _finish_with_message("NAA terminated because 'scholarly' is unavailable.")

    # --- 1: CPC L1 ---
    prompt_l1 = build_prompt_sys(SYS_PATENT_CLASSIFIER, TPL_CPC_L1, summary, cpc_level1_str)
    result_l1 = call_llm_json(client=client, model=model_name, tag="CPC-L1", prompt_text=prompt_l1, schema=SCHEMA_CPC_L1_CODES)
    level1_codes: List[str] = result_l1 if isinstance(result_l1, list) else []

    # --- 2: CPC L2 ---
    level2_parts: List[str] = []
    for sec in level1_codes:
        block = cpc_level2_map_str.get(sec)
        if block:
            level2_parts.append(f"### {sec}\n{block}")
    level2_options_str = "\n\n".join(level2_parts)
    level2_dict: Dict[str, str] = {}
    if level2_options_str.strip():
        prompt_l2 = build_prompt_sys(SYS_PATENT_CLASSIFIER, TPL_CPC_L2, summary, level2_options_str)
        result_l2 = call_llm_json(client=client, model=model_name, tag="CPC-L2", prompt_text=prompt_l2, schema=SCHEMA_CPC_L2_DICT)
        level2_dict = result_l2 if isinstance(result_l2, dict) else {}

    # --- 3: Innovation type ---
    taxonomy_text = format_innovation_taxonomy_text(INNOVATION_TYPE_DESCRIPTIONS)
    extended_summary = summary if not level2_dict else f"{summary}\n\n[CPC Level-2 selections]\n" + "\n".join(
        f"{k}: {v}" for k, v in level2_dict.items()
    )
    prompt_innov = build_prompt_sys(SYS_PATENT_CLASSIFIER, TPL_INNOVATION_TYPE, extended_summary, taxonomy_text)
    result_innov = call_llm_json(client=client, model=model_name, tag="TYPE", prompt_text=prompt_innov, schema=SCHEMA_INVENTION_TYPE)
    invention_type: InnovationType = (result_innov.get("invention_type", "none")  # type: ignore[assignment]
                                     if isinstance(result_innov, dict) else "none")
    if invention_type == "none":
        return _finish_with_message("NAA terminated because invention type is none.")

    # --- 4: Detail extraction (exhaustive) ---
    prompt_key, schema_obj = _detail_prompt_and_schema(invention_type)
    type_desc = INNOVATION_TYPE_DESCRIPTIONS[invention_type]  # type: ignore[index]
    prompt_detail = build_prompt_sys(SYS_PATENT_CLASSIFIER, prompt_key, summary, invention_type, type_desc, str(invention_pdf_uri))
    details_json = call_llm_json_with_pdf(
        client=client, model=model_name, tag="DETAIL", prompt_text=prompt_detail, schema=schema_obj, file_uri=invention_pdf_uri
    )
    if not isinstance(details_json, dict):
        return _finish_with_message("NAA terminated due to invalid detail JSON.")

    # --- 5: Enumerate ALL novelty aspects ---
    prompt_aspects = build_prompt_sys(
        SYS_PATENT_CLASSIFIER,
        TPL_NOVELTY_ASPECTS,
        json.dumps(details_json, ensure_ascii=False),
        invention_type,
        summary,
    )
    aspects_obj = call_llm_json(client=client, model=model_name, tag="NOVELTY-ASPECTS", prompt_text=prompt_aspects, schema=SCHEMA_NOVELTY_ASPECTS)
    aspects: List[str] = aspects_obj.get("aspects", []) if isinstance(aspects_obj, dict) else []
    aspects = [a for a in aspects if isinstance(a, str) and a.strip()]

    # --- 6: ONE Google Scholar query (LLM) targeting arXiv ---
    aspects_str = "\n".join(f"- {a}" for a in aspects) if aspects else "- (none)"
    prompt_query = build_prompt_sys(SYS_PATENT_CLASSIFIER, TPL_SCHOLAR_SINGLE_QUERY, invention_type, summary, aspects_str)
    q_obj = call_llm_json(client=client, model=model_name, tag="ARXIV-QUERY", prompt_text=prompt_query, schema=SCHEMA_SCHOLAR_SINGLE_QUERY)
    scholar_query: str = (q_obj.get("query") or "").strip() if isinstance(q_obj, dict) else ""
    if not scholar_query:
        return _finish_with_message("NAA terminated due to empty Scholar query.")

    print("\n" + "=" * 76)
    print("GOOGLE SCHOLAR SINGLE QUERY:\n", scholar_query)
    print("=" * 76)

    # --- 7: scholarly → arXiv PDF list ---
    arxiv_items = _search_google_scholar_serpapi_arxiv_pdfs(
        scholar_query, serpapi_key="", limit=int(cfg.get("per_page_k", 20))
    )
    # cap list
    arxiv_items = arxiv_items[:reference_max]

    # pretty print reference list
    print("\n" + "=" * 76)
    print(f"REFERENCE PDF LIST (arXiv only; first {len(arxiv_items)} of {len(arxiv_items)} total)")
    print("=" * 76)
    for i, it in enumerate(arxiv_items, 1):
        print(f"{i:02d}. {it.get('title','')} — {it.get('pdf_url','')}")
    print("=" * 76 + "\n")

    # --- 8: For each arXiv PDF — compare PDF vs PDF ---
    checks: List[Dict[str, Any]] = []
    for it in arxiv_items:
        pdf_url = (it.get("pdf_url") or "").strip()
        if not (pdf_url and invention_pdf_uri):
            continue  # strictly require both PDFs; no fallback
        comp = _compare_pdfs_with_invention(
            client=client, model=model_name,
            invention_pdf_uri=invention_pdf_uri,
            candidate_pdf_url=pdf_url
        )
        checks.append({
            "reference": it.get("abs_url", ""),
            "pdf_url": pdf_url,
            "title": it.get("title", ""),
            "enclosed": comp.get("overlap", []),
            "novelty": comp.get("novelty", []),
            "similarity": float(comp.get("similarity", 0.0)),
            "meta": {
                "year": it.get("year", ""),
                "source": "arxiv",
            }
        })
        time.sleep(compare_delay)

    # --- 9: Sort by similarity descending ---
    checks.sort(key=lambda x: x.get("similarity", 0.0), reverse=True)

    # --- Assemble artifacts ---
    naa_art: Dict[str, Any] = {
        "integrated": [],
        "detailed_checks": checks,
        "invention_type": invention_type,
        "invention_details": details_json,
        "sources": [search_backend],
        "model_version": "naa-scholar-v1",
        "generated_at": _now_iso(),
        "input_summary": summary,
        "cpc_level": {"level1": level1_codes, "level2": level2_dict},
        "doc_gcs_uri": invention_pdf_uri,
        "novelty_aspects": aspects,
        "search_query": scholar_query,
        "reference_pdfs": [{"title": it.get("title",""), "pdf_url": it.get("pdf_url",""), "abs_url": it.get("abs_url","")} for it in arxiv_items],
    }

    return {
        "artifacts": {"naa": naa_art},
        "internals": {"naa": [
            {"stage": "cpc_level1_classification", "codes": level1_codes},
            {"stage": "cpc_level2_classification", "dict": level2_dict},
            {"stage": "innovation_type_classification", "result": {"invention_type": invention_type}},
            {"stage": "detail_extraction", "schema_keys": list(schema_obj.get("properties", {}).keys())},
            {"stage": "novelty_aspects", "n_aspects": len(aspects)},
            {"stage": "scholar_single_query_llm", "query_len": len(scholar_query)},
            {"stage": "scholarly_backend", "backend": search_backend, "n_arxiv_pdfs": len(arxiv_items)},
            {"stage": "pdf_compare_llm", "n_compares": len(checks)},
        ]},
        "runtime": {"naa": {"status": "FINISHED", "route": []}},
        "message": "NAA completed: scholarly (arXiv-only PDFs) + direct PDF-to-PDF LLM comparison; results ranked by similarity.",
    }

# Export as Runnable
NOVELTY_A = RunnableLambda(naa_node)
