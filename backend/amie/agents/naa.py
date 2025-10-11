# amie/agents/naa.py
# NAA — full refs → Crossref DOIs → LLM ranking (baseline_top2 then innovation_top2) → OpenAlex resolve → cited-by
# Step 7 supports two modes:
#   - GCS mode (default): validated download → upload to GCS → LLM compare with two GCS URIs
#   - REMOTE mode (opt-in via config flag): skip GCS; pass remote PDF URL(s) directly to LLM
# Author: Harry (updated per spec)
# 2025-10-10

import os
import json
import time
import re
import random
import hashlib
import requests
from typing import Dict, Any, List, Optional, Tuple
from typing import Literal
from datetime import datetime, timezone
from urllib.parse import urlparse

from google import genai
from google.genai import types
from google.cloud import storage
from langchain_core.runnables import RunnableLambda
from ..state import GraphState

# ---------------------------------------------------------------------
# Type literals (English only)
# ---------------------------------------------------------------------
InnovationType = Literal["method", "structure", "unclear"]
SourceType = Literal["arxiv", "google_patents", "uspto"]

# ---------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------
MODEL_TEXT_DEFAULT = "gemini-2.0-flash-lite-001"
CROSSREF_BASE = "https://api.crossref.org"
OPENALEX_BASE = "https://api.openalex.org"
MAX_OPENALEX_BATCH = 50
OPENALEX_PAGE_SIZE = 200  # per OpenAlex docs
HTTP_TIMEOUT = (6, 30)  # (connect, read)
DEFAULT_POLITE_EMAIL = "zhanhaoc@oregonstate.edu"
MAX_CITEDBY_PAGES = 50  # safety cap

# --- Hard-coded GCP/GCS configuration (with env fallbacks) ---
GC_PROJECT = os.environ.get("GC_PROJECT", "aime-hello-world")
GCS_PREFIX = os.environ.get("GCS_PREFIX", "amie/pdf/")
GCS_BUCKET = os.environ.get("GCS_BUCKET", "aime-hello-world-amie-uswest1")
SIGNED_URL_TTL_SECONDS = int(os.environ.get("SIGNED_URL_TTL_SECONDS", str(7 * 24 * 3600)))

# ---------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------
def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d-%H-%M-%S")

def _truncate(s: str, n: int = 80) -> str:
    s = s or ""
    return s if len(s) <= n else s[:n] + "..."

def _normalize_title(t: str) -> str:
    return re.sub(r"\s+", " ", (t or "").strip().lower())

def _normalize_openalex_id(oid: str) -> str:
    """
    Accepts:
      - 'https://openalex.org/W123...'
      - 'openalex.org/W123...'
      - 'W123...'
    Returns: 'W123...'
    """
    oid = (oid or "").strip()
    if not oid:
        return ""
    if oid.startswith("http"):
        path = urlparse(oid).path or ""
        slug = path.rsplit("/", 1)[-1]
        return slug.strip()
    if "openalex.org/" in oid:
        slug = oid.rsplit("/", 1)[-1]
        return slug.strip()
    return oid

def _quiet_http_get(url: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    r = requests.get(url, params=params or {}, timeout=HTTP_TIMEOUT)
    r.raise_for_status()
    try:
        return r.json()
    except Exception:
        return {}

def _http_head_or_get_for_pdf(url: str) -> Tuple[str, Optional[str]]:
    """
    Try HEAD first with content negotiation; fall back to GET (small risk).
    Returns: (final_url, content_type) if reachable; else ("", None)
    """
    if not url:
        return "", None
    headers = {"Accept": "application/pdf, */*;q=0.1"}
    try:
        hr = requests.head(url, allow_redirects=True, timeout=HTTP_TIMEOUT, headers=headers)
        if 200 <= hr.status_code < 400:
            ctype = (hr.headers.get("Content-Type") or "").lower()
            return hr.url, ctype or None
    except Exception:
        pass
    try:
        gr = requests.get(url, allow_redirects=True, timeout=HTTP_TIMEOUT, headers=headers, stream=True)
        if 200 <= gr.status_code < 400:
            ctype = (gr.headers.get("Content-Type") or "").lower()
            return gr.url, ctype or None
    except Exception:
        pass
    return "", None

def _pretty(obj: Any, max_len: int = 4000) -> str:
    try:
        s = json.dumps(obj, ensure_ascii=False, indent=2)
    except Exception:
        s = str(obj)
    if len(s) > max_len:
        return s[:max_len] + "\n... [truncated]"
    return s

def _llm_json_with_parts(client: "genai.Client", model: str,
                         parts: List[Any], prompt_text: str,
                         schema: Dict[str, Any]) -> Any:
    print(f"[NAA] [LLM prompt]\n{prompt_text}")
    resp = client.models.generate_content(
        model=model,
        contents=parts + [prompt_text],
        config=genai.types.GenerateContentConfig(
            response_schema=schema,
            response_mime_type="application/json"
        ),
    )
    text = getattr(resp, "text", "") or ""
    return json.loads(text)

def _llm_json_text(client: "genai.Client", model: str,
                   prompt_text: str, schema: Dict[str, Any],
                   prompt_log: Optional[str] = None) -> Any:
    print(f"[NAA] [LLM prompt]\n{prompt_log if prompt_log is not None else prompt_text}")
    resp = client.models.generate_content(
        model=model,
        contents=[prompt_text],
        config=genai.types.GenerateContentConfig(
            response_schema=schema,
            response_mime_type="application/json"
        ),
    )
    text = getattr(resp, "text", "") or ""
    return json.loads(text)

def _strip_bracket_prefix(cite: str) -> str:
    if not isinstance(cite, str):
        return cite
    s = re.sub(r'^\s*\[\s*\d*\s*\]\s*', '', cite).strip()
    s = re.sub(r'\s+', ' ', s)
    return s

def _ensure_pdf_url(url: str) -> str:
    """
    Convert common non-direct links into direct PDFs where possible:
      - arXiv: /abs/{id} -> /pdf/{id}.pdf ; ensure .pdf suffix
      - *.pdf -> return as-is
    Otherwise return original.
    """
    u = (url or "").strip()
    if not u:
        return ""
    lower = u.lower()
    if lower.endswith(".pdf"):
        return u
    if "arxiv.org/abs/" in lower:
        tail = u.split("/abs/", 1)[-1].split("?")[0].strip("/")
        return f"https://arxiv.org/pdf/{tail}.pdf"
    if "arxiv.org/pdf/" in lower and not lower.endswith(".pdf"):
        return u.rstrip("/") + ".pdf"
    return u

def _looks_like_pdf(data: bytes) -> bool:
    if not data or len(data) < 10:
        return False
    return data[:5] == b"%PDF-"

def _download_pdf_validated(url: str) -> Tuple[bytes, str, str]:
    """
    Download with redirects and validate it's a PDF.
    Returns: (bytes, resolved_url, content_type)
    Raises on non-200 or non-PDF payload.
    """
    u = _ensure_pdf_url(url)
    resp = requests.get(u, timeout=HTTP_TIMEOUT, allow_redirects=True)
    resp.raise_for_status()
    data = resp.content or b""
    ctype = (resp.headers.get("Content-Type") or "").lower()
    if ("pdf" not in ctype) and (not _looks_like_pdf(data)):
        print(f"[NAA] [step 7] download not PDF | content-type={ctype} | resolved_url={resp.url} | size={len(data)}")
        raise RuntimeError("Downloaded content is not a valid PDF.")
    return data, resp.url, ctype

def _gcs_upload_bytes(storage_client: storage.Client, bucket_name: str, object_path: str,
                      data: bytes, content_type: str = "application/pdf") -> str:
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(object_path)
    blob.upload_from_string(data, content_type=content_type or "application/pdf")
    return f"gs://{bucket_name}/{object_path}"

# ---------------------------------------------------------------------
# Early-exit (FAILED) helper
# ---------------------------------------------------------------------
def _fail(msg: str, state: GraphState, *, internals_note: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    idca = (state.get("artifacts", {}) or {}).get("idca", {}) if isinstance(state.get("artifacts"), dict) else {}
    summary = idca.get("summary", "") if isinstance(idca, dict) else ""
    doc_gcs_uri = idca.get("doc_gcs_uri") if isinstance(idca, dict) and idca.get("doc_gcs_uri") else state.get("doc_gcs_uri", "")

    naa_art = {
        "core_subject": "",
        "reference_urls": [],
        "top2_cited_by": [],
        "input_summary": summary,
        "doc_gcs_uri": doc_gcs_uri,
        "generated_at": _now_iso(),
    }
    naa_internals = {"error": msg}
    if internals_note:
        naa_internals.update(internals_note)

    print(f"[NAA] FAIL: {msg}")
    return {
        "artifacts": {"naa": naa_art},
        "internals": {"naa": naa_internals},
        "runtime": {"naa": {"status": "FAILED", "route": []}},
        "message": msg,
    }

# ---------------------------------------------------------------------
# Crossref
# ---------------------------------------------------------------------
def _crossref_biblio(cite_str: str, mailto: Optional[str]) -> Dict[str, Any]:
    if not cite_str or not cite_str.strip():
        return {}
    params = {"query.bibliographic": cite_str, "rows": 1}
    if mailto:
        params["mailto"] = mailto
    js = _quiet_http_get(f"{CROSSREF_BASE}/works", params=params)
    items = js.get("message", {}).get("items") or []
    if not items:
        return {}
    it = items[0]
    doi = (it.get("DOI") or "").strip()
    title = (it.get("title") or [""])[0]
    url = (it.get("URL") or "").strip()
    pdf_url = ""
    for link in it.get("link", []) or []:
        if link.get("content-type") == "application/pdf":
            pdf_url = (link.get("URL") or "").strip()
            break
    return {"doi": doi, "title": title, "url": url, "pdf_url": pdf_url, "raw": cite_str}

# ---------------------------------------------------------------------
# OpenAlex
# ---------------------------------------------------------------------
def _chunk(lst: List[str], n: int) -> List[List[str]]:
    return [lst[i:i+n] for i in range(0, len(lst), n)]

def _openalex_by_dois(dois: List[str], mailto: Optional[str]) -> List[Dict[str, Any]]:
    if not dois:
        return []
    out: List[Dict[str, Any]] = []
    for group in _chunk([d for d in dois if d], MAX_OPENALEX_BATCH):
        filt = "doi:" + "|".join(group)
        params = {"filter": filt, "per-page": min(len(group), 50)}
        if mailto:
            params["mailto"] = mailto
        js = _quiet_http_get(f"{OPENALEX_BASE}/works", params=params)
        results = js.get("results") or []
        for w in results:
            doi_url = (w.get("doi") or "").replace("https://doi.org/", "")
            best_oa = w.get("best_oa_location") or {}
            out.append({
                "title": w.get("title") or "",
                "doi": doi_url,
                "url": w.get("primary_location", {}).get("landing_page_url") or (f"https://doi.org/{doi_url}" if doi_url else ""),
                "pdf_url": best_oa.get("pdf_url") or "",
                "year": str(w.get("publication_year") or ""),
                "openalex_id": w.get("id") or "",
                "cited_by_count": w.get("cited_by_count") or 0,
                "cited_by_api_url": w.get("cited_by_api_url") or "",
            })
        time.sleep(0.1)
    return out

def _openalex_search_title(title: str, mailto: Optional[str]) -> Dict[str, Any]:
    if not title.strip():
        return {}
    params = {"search": title, "per-page": 1}
    if mailto:
        params["mailto"] = mailto
    js = _quiet_http_get(f"{OPENALEX_BASE}/works", params=params)
    results = js.get("results") or []
    if not results:
        return {}
    w = results[0]
    doi_url = (w.get("doi") or "").replace("https://doi.org/", "")
    best_oa = w.get("best_oa_location") or {}
    return {
        "title": w.get("title") or "",
        "doi": doi_url,
        "url": w.get("primary_location", {}).get("landing_page_url") or (f"https://doi.org/{doi_url}" if doi_url else ""),
        "pdf_url": best_oa.get("pdf_url") or "",
        "year": str(w.get("publication_year") or ""),
        "openalex_id": w.get("id") or "",
        "cited_by_count": w.get("cited_by_count") or 0,
        "cited_by_api_url": w.get("cited_by_api_url") or "",
    }

def _openalex_fetch_cited_by_via_filter(slug: str, mailto: Optional[str]) -> List[Dict[str, Any]]:
    params: Dict[str, Any] = {
        "filter": f"cites:{slug}",
        "per-page": OPENALEX_PAGE_SIZE,
        "cursor": "*",
    }
    if mailto:
        params["mailto"] = mailto

    out: List[Dict[str, Any]] = []
    pages = 0
    while True:
        pages += 1
        if pages > MAX_CITEDBY_PAGES:
            print(f"[NAA] [cited-by] reached page cap ({MAX_CITEDBY_PAGES}) for {slug}, stopping.")
            break
        js = _quiet_http_get(f"{OPENALEX_BASE}/works", params=params)
        results = js.get("results") or []
        for w in results:
            out.append({
                "title": w.get("title") or "",
                "url": (w.get("primary_location") or {}).get("landing_page_url") or "",
                "openalex_id": w.get("id") or "",
                "year": str(w.get("publication_year") or ""),
            })
        next_cursor = (js.get("meta") or {}).get("next_cursor")
        if not next_cursor:
            break
        params["cursor"] = next_cursor
        time.sleep(0.08)
    return out

def _openalex_fetch_cited_by(oaid_or_url: str, cited_by_api_url: str, mailto: Optional[str], expected_total: Optional[int]) -> List[Dict[str, Any]]:
    slug = _normalize_openalex_id(oaid_or_url)
    out: List[Dict[str, Any]] = []
    pages = 0

    if cited_by_api_url:
        base_url = cited_by_api_url
        params: Dict[str, Any] = {"per-page": OPENALEX_PAGE_SIZE, "cursor": "*"}
        if mailto:
            params["mailto"] = mailto
    else:
        base_url = f"{OPENALEX_BASE}/works"
        params = {"filter": f"cites:{slug}", "per-page": OPENALEX_PAGE_SIZE, "cursor": "*"}
        if mailto:
            params["mailto"] = mailto

    while True:
        pages += 1
        if pages > MAX_CITEDBY_PAGES:
            print(f"[NAA] [cited-by] page cap ({MAX_CITEDBY_PAGES}) reached for {slug}, stopping.")
            break
        js = _quiet_http_get(base_url, params=params)
        results = js.get("results") or []
        for w in results:
            out.append({
                "title": w.get("title") or "",
                "url": (w.get("primary_location") or {}).get("landing_page_url") or "",
                "openalex_id": w.get("id") or "",
                "year": str(w.get("publication_year") or ""),
            })
        if isinstance(expected_total, int) and expected_total > 0 and len(out) >= expected_total:
            break
        next_cursor = (js.get("meta") or {}).get("next_cursor")
        if not next_cursor:
            break
        params["cursor"] = next_cursor
        time.sleep(0.08)

    return out

# ---------------------------------------------------------------------
# PDF candidate harvesting
# ---------------------------------------------------------------------
def _resolve_pdf_via_content_negotiation(doi_or_url: str) -> str:
    """
    Try to reach a direct PDF by content negotiation starting from a DOI (https://doi.org/{doi})
    or a landing URL. Return the final URL if it looks like a PDF target (content-type hints or .pdf).
    """
    if not doi_or_url:
        return ""
    # If it's a bare DOI, normalize to doi.org
    if doi_or_url and not doi_or_url.lower().startswith("http"):
        doi_or_url = f"https://doi.org/{doi_or_url}"
    final_url, ctype = _http_head_or_get_for_pdf(doi_or_url)
    if not final_url:
        return ""
    lower = (ctype or "").lower()
    if "pdf" in lower or final_url.lower().endswith(".pdf"):
        return final_url
    return ""

def _candidate_from_record(item: Dict[str, Any]) -> Optional[Dict[str, str]]:
    """Produce a single candidate {title,pdf_url,year} if available."""
    w = item.get("openalex_work", {}) or {}
    cr = item.get("crossref", {}) or {}
    title = (w.get("title") or "").strip() or (cr.get("title") or "").strip()
    year = (w.get("year") or "").strip()
    pdf = (w.get("pdf_url") or "").strip() or (cr.get("pdf_url") or "").strip()
    if not pdf:
        # Try arXiv transform on known landing URLs
        landing = (w.get("url") or "").strip() or (cr.get("url") or "").strip()
        pdf = _ensure_pdf_url(landing)
    if not pdf:
        # Try DOI → content negotiation
        doi = (cr.get("doi") or w.get("doi") or "").strip()
        pdf = _resolve_pdf_via_content_negotiation(doi)
    if not pdf:
        # Try landing again via content negotiation
        landing = (w.get("url") or "").strip() or (cr.get("url") or "").strip()
        pdf = _resolve_pdf_via_content_negotiation(landing)
    if pdf:
        return {"title": title or "network_pdf", "pdf_url": pdf, "year": year}
    return None

def _harvest_pdf_candidates(resolved_results: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    """Return candidate list with best-effort PDF URLs from resolved references."""
    out: List[Dict[str, str]] = []
    for item in resolved_results:
        cand = _candidate_from_record(item)
        if cand:
            # Normalize arXiv pdf suffix
            cand["pdf_url"] = _ensure_pdf_url(cand["pdf_url"])
            out.append(cand)
    print(f"[NAA] [step 7] harvested PDF candidates: {len(out)}")
    return out

# ---------------------------------------------------------------------
# Dedup helper
# ---------------------------------------------------------------------
def _dedup_resolved(results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen = set()
    out: List[Dict[str, Any]] = []

    def make_key(item: Dict[str, Any]) -> str:
        w = item.get("openalex_work") or {}
        cr = item.get("crossref") or {}
        openalex_id = _normalize_openalex_id((w.get("openalex_id") or "").strip())
        doi = (cr.get("doi") or w.get("doi") or "").strip().lower()
        if openalex_id:
            return f"oa:{openalex_id.lower()}"
        if doi:
            return f"doi:{doi}"
        t = _normalize_title(cr.get("title") or w.get("title") or "")
        y = (w.get("year") or "").strip()
        return f"ty:{t}|{y}"

    for item in results:
        key = make_key(item)
        if key and key not in seen:
            seen.add(key)
            out.append(item)
    return out

# ---------------------------------------------------------------------
# Main NAA node
# ---------------------------------------------------------------------
def naa_node(state: GraphState, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    print("[NAA] start")

    # Upstream check — FINISHED means summary and required attributes exist
    idca_status = state.get("runtime", {}).get("idca", {}).get("status")
    print(f"[NAA] upstream status: {idca_status}")
    if idca_status != "FINISHED":
        return _fail("[NAA] Upstream not finished", state)

    # Target PDF + summary
    idca_art = (state.get("artifacts", {}) or {}).get("idca", {}) if isinstance(state.get("artifacts"), dict) else {}
    tar_gcs_uri: str = idca_art.get("doc_gcs_uri") or state.get("doc_gcs_uri") or ""
    idca_summary: str = idca_art.get("summary", "") if isinstance(idca_art, dict) else ""
    print(f"[NAA] doc_gcs_uri (original): {tar_gcs_uri}")
    if not tar_gcs_uri:
        return _fail("[NAA] No invention PDF found (idca.doc_gcs_uri).", state, internals_note={"where": "precheck"})

    # Config (LLM + polite email + Step7 switches)
    cfg = (config or {}).get("configurable", {})
    if not cfg:
        return _fail("[NAA] No config found", state, internals_note={"where": "precheck"})
    client: "genai.Client" = cfg.get("genai_client")
    if not client:
        return _fail("[NAA] No genai client found", state, internals_note={"where": "precheck"})
    model_name = cfg.get("model_name", MODEL_TEXT_DEFAULT) or MODEL_TEXT_DEFAULT
    polite_email: Optional[str] = cfg.get("mailto") or DEFAULT_POLITE_EMAIL

    # Step7 controls
    step7_remote: bool = bool(cfg.get("naa_step7_remote", False))
    step7_override: Optional[Dict[str, str]] = cfg.get("naa_step7_override_pdf") if isinstance(cfg.get("naa_step7_override_pdf"), dict) else None

    print(f"[NAA] client={type(client)} model={model_name} mailto={polite_email} step7_remote={step7_remote}")

    # ------------------ Step 1: extract full reference list ------------------
    print("[NAA] [step 1] extract full reference list — start")
    schema_refs = {"type": "array", "items": {"type": "string"}}
    prompt_refs = (
        "Extract the complete reference list from the paper. "
        "For each reference, output a clean plain-text string that includes: full list of authors, paper title, and year (if available). "
        "You may include journal or conference name and volume/page information as optional additions. "
        "The format should be natural and readable, without quotation marks or index numbers. "
        "Return only a JSON array of strings, with no explanations or extra formatting."
    )
    try:
        refs_raw = _llm_json_with_parts(
            client=client, model=model_name,
            parts=[types.Part.from_uri(file_uri=tar_gcs_uri, mime_type="application/pdf")],
            prompt_text=prompt_refs, schema=schema_refs
        )
    except Exception as e:
        return _fail(f"[NAA] step 1 LLM failed: {e}", state, internals_note={"stage": "step1"})

    references_all: List[str] = [_strip_bracket_prefix(r) for r in refs_raw if isinstance(r, str) and r.strip()]
    print(f"[NAA] [step 1] refs extracted: {len(references_all)}")
    try:
        print(json.dumps(references_all[:3], indent=4))
    except Exception:
        print(json.dumps([str(x) for x in references_all[:3]], indent=4))

    if not references_all:
        return _fail("[NAA] step 1 produced empty reference list", state, internals_note={"stage": "step1"})

    # ------------------ Step 2: resolve all DOIs via Crossref ------------------
    print(f"[NAA] [step 2] resolve DOIs via Crossref — start (n={len(references_all)})")
    try:
        crossref_hits = [_crossref_biblio(r, polite_email) for r in references_all]
    except Exception as e:
        return _fail(f"[NAA] step 2 Crossref failed: {e}", state, internals_note={"stage": "step2"})

    ref2meta: Dict[str, Dict[str, Any]] = {}
    doi_count = 0
    for raw, meta in zip(references_all, crossref_hits):
        key = raw.strip()
        ref2meta[key] = meta
        if meta.get("doi"):
            doi_count += 1

    print(f"[NAA] [step 2] DOIs resolved: {doi_count}/{len(references_all)}")
    preview = []
    for m in crossref_hits[:3]:
        t = (m.get("title") or "") if isinstance(m, dict) else ""
        d = (m.get("doi") or "") if isinstance(m, dict) else ""
        preview.append(_truncate(f"title={t} | doi={d}", 80))
    print(json.dumps(preview, indent=4))

    # ------------------ Step 3: LLM ranking (baseline_top2) ------------------
    print("[NAA] [step 3] LLM ranking — baseline_top2")
    schema_baseline = {"type": "object","properties":{"baseline_top2":{"type":"array","items":{"type":"string"}}},"required":["baseline_top2"]}
    refs_for_llm_full = json.dumps(references_all, ensure_ascii=False)
    refs_for_log = _truncate(refs_for_llm_full, 80)
    prompt_baseline_full = (
        "You are given the full reference list as a JSON array of strings. "
        "Select the two references most likely used as baselines (canonical prior work). "
        "Return only JSON with key baseline_top2, containing exactly two strings copied verbatim from the input array."
        f"\n\nREFERENCES_JSON:\n{refs_for_llm_full}\n"
    )
    prompt_baseline_log = (
        "You are given the full reference list as a JSON array of strings. "
        "Select the two references most likely used as baselines (canonical prior work). "
        "Return only JSON with key baseline_top2, containing exactly two strings copied verbatim from the input array."
        f"\n\nREFERENCES_JSON:\n{refs_for_log}\n"
    )
    try:
        baseline_obj = _llm_json_text(client=client, model=model_name, prompt_text=prompt_baseline_full, schema=schema_baseline, prompt_log=prompt_baseline_log)
    except Exception as e:
        return _fail(f"[NAA] step 3 baseline ranking LLM failed: {e}", state, internals_note={"stage": "step3"})

    baseline_top2: List[str] = [s for s in (baseline_obj.get("baseline_top2") or []) if isinstance(s, str) and s.strip()]
    print(f"[NAA] [step 3] baseline_top2 count={len(baseline_top2)}")
    try:
        print(json.dumps(baseline_top2, indent=4, ensure_ascii=False))
    except Exception:
        print(json.dumps([str(x) for x in baseline_top2], indent=4))
    if len(baseline_top2) != 2:
        return _fail("[NAA] step 3 did not return exactly two baseline items", state, internals_note={"stage": "step3", "rank": baseline_obj})

    # ------------------ Step 4: LLM ranking (innovation_top2) ------------------
    print("[NAA] [step 4] LLM ranking — innovation_top2 (with exclusions and no year filter)")
    schema_innov = {
        "type": "object",
        "properties": {"innovation_top2": {"type": "array", "items": {"type": "string"}}},
        "required": ["innovation_top2"]
    }

    prompt_innov_full = (
        "You are given the full reference list as a JSON array of strings.\n"
        "Task: Select EXACTLY TWO references that most likely provide the paper’s CORE innovative ideas.\n\n"
        "Strong preferences:\n"
        "  • Prefer research articles (journal or conference papers) that introduce a NEW method, system, structure, or theory.\n"
        "  • Prefer works that are likely directly built upon in the paper (inherited, extended, or combined), i.e., concrete technical bases.\n"
        "Strict exclusions (DO NOT select):\n"
        "  • Textbooks (e.g., “Textbook”, “Handbook”, “Encyclopedia”, “Lecture Notes”).\n"
        "  • Manuals (e.g., “Manual”, “User Guide”, “Programming Guide”, “Developer Guide”).\n"
        "  • General-purpose user documentation or software guides.\n"
        "Notes:\n"
        "  • Do NOT use publication year as a filtering criterion; older but seminal work can still be selected.\n"
        "  • You MUST avoid choosing any item already selected as baselines.\n"
        "Output format (MUST follow exactly):\n"
        '  {"innovation_top2": [<verbatim ref string>, <verbatim ref string>]}\n'
        "Rules:\n"
        "  • Return a valid JSON object with key 'innovation_top2'.\n"
        "  • Each chosen string MUST be copied VERBATIM from the input list (no rewriting, no translation, no reformatting).\n"
        "  • Choose exactly two items.\n"
        f"\nALREADY_SELECTED_BASELINES:\n{json.dumps(baseline_top2, ensure_ascii=False)}\n"
        f"\nREFERENCES_JSON:\n{refs_for_llm_full}\n"
    )

    refs_for_log = _truncate(refs_for_llm_full, 80)
    prompt_innov_log = (
        "You are given the full reference list as a JSON array of strings.\n"
        "Task: Select EXACTLY TWO references that most likely provide the paper’s CORE innovative ideas.\n"
        "Prefer research articles with NEW method/system/structure/theory; avoid textbooks/manuals/user guides/programming guides.\n"
        "No year-based filtering. Avoid items already selected as baselines.\n"
        "Return ONLY a JSON object: {\"innovation_top2\": [str, str]} with verbatim strings.\n"
        f"\nALREADY_SELECTED_BASELINES (truncated):\n{_truncate(json.dumps(baseline_top2, ensure_ascii=False), 80)}\n"
        f"\nREFERENCES_JSON (truncated):\n{refs_for_log}\n"
    )

    try:
        innovation_obj = _llm_json_text(
            client=client,
            model=model_name,
            prompt_text=prompt_innov_full,
            schema=schema_innov,
            prompt_log=prompt_innov_log
        )
    except Exception as e:
        return _fail(f"[NAA] step 4 innovation ranking LLM failed: {e}", state, internals_note={"stage": "step4"})

    innovation_top2: List[str] = [s for s in (innovation_obj.get("innovation_top2") or []) if isinstance(s, str) and s.strip()]
    print(f"[NAA] [step 4] innovation_top2 count={len(innovation_top2)}")
    try:
        print(json.dumps(innovation_top2, indent=4, ensure_ascii=False))
    except Exception:
        print(json.dumps([str(x) for x in innovation_top2], indent=4))
    if len(innovation_top2) != 2:
        return _fail("[NAA] step 4 did not return exactly two innovation items", state, internals_note={"stage": "step4", "rank": innovation_obj})

    # ------------------ Step 5: OpenAlex resolve (works) ------------------
    print("[NAA] [step 5] OpenAlex resolve — start")
    selected_refs = baseline_top2 + innovation_top2
    resolved_results: List[Dict[str, Any]] = []

    for label, group in [("baseline", baseline_top2), ("innovation", innovation_top2)]:
        for ref_str in group:
            meta = ref2meta.get(ref_str.strip()) or {}
            doi = meta.get("doi", "")
            title = meta.get("title", "") or ref_str

            work: Dict[str, Any] = {}
            try:
                if doi:
                    works = _openalex_by_dois([doi], polite_email)
                    if works:
                        work = works[0]
                if not work:
                    work = _openalex_search_title(title, polite_email)
            except Exception as e:
                print(f"[NAA] [step 5] resolve error for ref '{_truncate(title,80)}': {e}")
                work = {}

            resolved_results.append({
                "label": label,
                "reference_string": ref_str,
                "crossref": {
                    "title": meta.get("title", ""),
                    "doi": doi,
                    "url": meta.get("url", ""),
                    "pdf_url": meta.get("pdf_url", "")
                },
                "openalex_work": work,
                "cited_by": []
            })

    resolved_ok = sum(1 for it in resolved_results if (it.get("openalex_work") or {}).get("openalex_id") or (it.get("openalex_work") or {}).get("url"))
    print(f"[NAA] [step 5] OpenAlex resolve: {resolved_ok}/{len(resolved_results)}")

    before = len(resolved_results)
    deduped = _dedup_resolved(resolved_results)
    after = len(deduped)
    print(f"[NAA] [step 5] deduplicated: {before} -> {after} (key order: openalex_id|doi|title+year)")
    resolved_results = deduped

    # ------------------ Step 6: OpenAlex cited-by via cites-filter ------------------
    print("[NAA] [step 6] OpenAlex cited-by — start (cites:W...) per docs)")
    for idx, item in enumerate(resolved_results, start=1):
        w = item.get("openalex_work") or {}
        raw_oaid = w.get("openalex_id", "")
        slug = _normalize_openalex_id(raw_oaid)
        expected_count = w.get("cited_by_count")
        api_url = w.get("cited_by_api_url") or ""
        try:
            if slug:
                cb = _openalex_fetch_cited_by(
                    oaid_or_url=slug,
                    cited_by_api_url=api_url,
                    mailto=polite_email,
                    expected_total=expected_count if isinstance(expected_count, int) else None,
                )
            else:
                cb = []
            item["cited_by"] = cb
            print(f"[NAA] [step 6] cited-by fetched for {idx}/{len(resolved_results)} — oaid={slug or 'NA'} expected={expected_count or 0} got={len(cb)}")
        except Exception as e:
            print(f"[NAA] [step 6] cited-by error for {idx}/{len(resolved_results)} (oaid={slug or 'NA'}): {e}")
            item["cited_by"] = []

    # ------------------ Step 7: Pairwise PDF comparison ------------------
    print(f"[NAA] [step 7] mode={'REMOTE' if step7_remote else 'GCS'} — pairwise PDF compare")

    step7_result: Dict[str, Any] = {"status": "unclear"}
    network_gcs_uri = ""
    network_remote_url = ""

    # Choose candidate (override OR harvested)
    if step7_override and isinstance(step7_override.get("pdf_url"), str):
        net_title = (step7_override.get("title") or "").strip() or "network_pdf"
        net_pdf_url = _ensure_pdf_url(step7_override["pdf_url"].strip())
        print(f"[NAA] [step 7] override in config: title='{net_title}', pdf='{net_pdf_url}'")
        chosen = {"title": net_title, "pdf_url": net_pdf_url, "year": ""}
    else:
        candidates_any = _harvest_pdf_candidates(resolved_results)

        # Prefer last 10 years if available
        cur_year = datetime.now(timezone.utc).year
        min_year = cur_year - 10

        def _is_recent(ystr: str) -> bool:
            try:
                y = int(ystr)
                return y >= min_year
            except Exception:
                return False

        candidates_recent = [c for c in candidates_any if _is_recent(c.get("year", ""))]
        pool = candidates_recent if candidates_recent else candidates_any
        if not pool:
            print("[NAA] [step 7] no reference has a usable PDF URL; skipping comparison.")
            chosen = None
        else:
            chosen = random.choice(pool)

    # REMOTE mode
    if step7_remote and chosen:
        net_title = chosen["title"]
        network_remote_url = chosen["pdf_url"]
        print(f"[NAA] [step 7][REMOTE] Using remote URL directly: {network_remote_url}")

        compare_schema = {
            "type": "object",
            "properties": {
                "network_title": {"type": "string"},
                "network_pdf_url": {"type": "string"},
                "same": {"type": "array", "items": {"type": "string"}},
                "new": {"type": "array", "items": {"type": "string"}}
            },
            "required": ["network_title", "network_pdf_url", "same", "new"]
        }

        parts: List[Any] = []
        try:
            parts.append(types.Part.from_uri(file_uri=tar_gcs_uri, mime_type="application/pdf"))
        except Exception as e:
            print(f"[NAA] [step 7][REMOTE] failed to attach ORIGINAL by URI: {e}")

        try:
            parts.append(types.Part.from_uri(file_uri=network_remote_url, mime_type="application/pdf"))
        except Exception as e:
            print(f"[NAA] [step 7][REMOTE] failed to attach NETWORK by URI: {e}")

        prompt_compare = (
            "You are given TWO documents for comparison. When available, also use the provided URLs:\n"
            "  (A) ORIGINAL/target invention document.\n"
            "  (B) PRIOR reference (network PDF).\n\n"
            "If binary attachments are accessible, analyze them. If not, fetch and analyze via the URLs.\n"
            "Goal: Compare (A) vs (B) at the technical level.\n"
            "  • 'same': overlapping technical elements in BOTH (A) and (B).\n"
            "  • 'new': elements that appear in (A) but NOT in (B) — A’s novel contributions over B.\n"
            "Keep bullets short (<= 25 words) and specific.\n"
            "If unclear, write 'unclear'. Return JSON with keys: network_title, network_pdf_url, same, new."
        )

        try:
            compare_obj = _llm_json_with_parts(
                client=client,
                model=model_name,
                parts=parts,
                prompt_text=(
                    f"{prompt_compare}\n"
                    f"ORIGINAL_PDF_GCS: {tar_gcs_uri}\n"
                    f"NETWORK_TITLE: {net_title}\n"
                    f"NETWORK_PDF_URL: {network_remote_url}\n"
                ),
                schema=compare_schema
            )
            compare_obj["network_title"] = net_title
            compare_obj["network_pdf_url"] = network_remote_url
            compare_obj["network_pdf_gcs"] = ""
            step7_result = compare_obj
        except Exception as e:
            print(f"[NAA] [step 7][REMOTE] LLM comparison failed: {e}")
            step7_result = {"status": "unclear", "reason": f"llm_error_remote: {e}", "network_pdf_url": network_remote_url, "network_pdf_gcs": ""}

    # GCS mode
    if (not step7_remote) and chosen:
        net_title = chosen["title"]
        net_pdf_url = chosen["pdf_url"]
        try:
            pdf_bytes, resolved_url, ctype = _download_pdf_validated(net_pdf_url)
            print(f"[NAA] [step 7][GCS] DOWNLOAD OK | original_url={net_pdf_url} | resolved_url={resolved_url} | size={len(pdf_bytes)} | ctype={ctype}")
        except Exception as e:
            print(f"[NAA] [step 7][GCS] download failed/invalid: {e}")
            step7_result = {"status": "unclear", "reason": f"download_error: {e}"}
            pdf_bytes = None

        if pdf_bytes:
            try:
                storage_client = storage.Client(project=GC_PROJECT)
                sha1 = hashlib.sha1(net_pdf_url.encode("utf-8")).hexdigest()[:12]
                obj_path = f"{GCS_PREFIX.rstrip('/')}/netpdf_{_now_iso()}_{sha1}.pdf"
                network_gcs_uri = _gcs_upload_bytes(storage_client, GCS_BUCKET, obj_path, pdf_bytes, content_type="application/pdf")
                print(f"[NAA] [step 7][GCS] original_gcs_uri: {tar_gcs_uri}")
                print(f"[NAA] [step 7][GCS] network_gcs_uri:  {network_gcs_uri}")
            except Exception as e:
                print(f"[NAA] [step 7][GCS] GCS upload failed: {e}")
                step7_result = {"status": "unclear", "reason": f"gcs_upload_error: {e}"}
                network_gcs_uri = ""

            if network_gcs_uri:
                compare_schema = {
                    "type": "object",
                    "properties": {
                        "network_title": {"type": "string"},
                        "network_pdf_gcs": {"type": "string"},
                        "same": {"type": "array", "items": {"type": "string"}},
                        "new": {"type": "array", "items": {"type": "string"}}
                    },
                    "required": ["network_title", "network_pdf_gcs", "same", "new"]
                }
                prompt_compare = (
                    "You are given TWO PDFs as cloud URIs:\n"
                    "  (A) The ORIGINAL/target invention document.\n"
                    "  (B) A PRIOR reference (network PDF).\n\n"
                    "Goal: Compare (A) vs (B) at the technical level.\n"
                    "  • 'same': concise bullet points describing overlapping technical elements in BOTH (A) and (B).\n"
                    "  • 'new': concise bullet points describing elements that appear in (A) but NOT in (B)—A’s novel contributions over B.\n"
                    "Keep bullets short (<= 25 words) and specific.\n"
                    "If unclear, write 'unclear'. Return JSON with keys: network_title, network_pdf_gcs, same, new.\n"
                )
                try:
                    compare_obj = _llm_json_with_parts(
                        client=client,
                        model=model_name,
                        parts=[
                            types.Part.from_uri(file_uri=tar_gcs_uri, mime_type="application/pdf"),
                            types.Part.from_uri(file_uri=network_gcs_uri, mime_type="application/pdf"),
                        ],
                        prompt_text=(
                            f"{prompt_compare}"
                            f"\nORIGINAL_PDF_GCS:\n{tar_gcs_uri}\n"
                            f"NETWORK_TITLE:\n{net_title}\n"
                            f"NETWORK_PDF_GCS:\n{network_gcs_uri}\n"
                        ),
                        schema=compare_schema
                    )
                    compare_obj["network_title"] = net_title
                    compare_obj["network_pdf_gcs"] = network_gcs_uri
                    compare_obj["network_pdf_url"] = ""
                    step7_result = compare_obj
                except Exception as e:
                    print(f"[NAA] [step 7][GCS] LLM comparison failed (GCS URIs): {e}")
                    step7_result = {"status": "unclear", "reason": f"llm_error_gcs: {e}", "network_pdf_gcs": network_gcs_uri, "network_pdf_url": ""}

    # ===== Final detailed print =====
    final_view = []
    for item in resolved_results:
        w = item.get("openalex_work", {}) or {}
        final_view.append({
            "label": item.get("label", ""),
            "ref_title": item.get("crossref", {}).get("title") or w.get("title") or "",
            "ref_doi": item.get("crossref", {}).get("doi") or w.get("doi") or "",
            "openalex_id": _normalize_openalex_id(w.get("openalex_id", "")),
            "year": w.get("year", ""),
            "url": w.get("url", ""),
            "pdf_url": w.get("pdf_url", ""),
            "cited_by_count": len(item.get("cited_by", [])),
        })
    print(f"[NAA] [final] resolved (unique refs + cited-by counts):\n{_pretty(final_view)}")
    print(f"[NAA] [final] step7 compare result:\n{_pretty(step7_result)}")

    # ------------------ Success assembly ------------------
    naa_art = {
        "core_subject": "",
        "reference_urls": resolved_results,
        "top2_cited_by": [],
        "input_summary": idca_summary,
        "doc_gcs_uri": tar_gcs_uri,
        "generated_at": _now_iso(),
        "temp_step7": step7_result
    }
    naa_internals = {
        "log": f"completed: refs → crossref → baseline_llm → innovation_llm → openalex_resolve(dedup) → openalex_citedby(cites-filter) → step7_compare({'REMOTE' if step7_remote else 'GCS'})",
        "counts": {
            "refs_total": len(references_all),
            "dois_resolved": doi_count,
            "baseline_top2": len(baseline_top2),
            "innovation_top2": len(innovation_top2),
            "openalex_resolved_ok": resolved_ok,
            "unique_after_dedup": len(resolved_results)
        }
    }

    return {
        "artifacts": {"naa": naa_art},
        "internals": {"naa": naa_internals},
        "runtime": {"naa": {"status": "FINISHED", "route": []}},
        "message": "NAA: refs resolved (deduped), cited-by via cites-filter, and Step 7 comparison completed (REMOTE or GCS mode)"
    }

# Export as Runnable
NOVELTY_A = RunnableLambda(naa_node)
