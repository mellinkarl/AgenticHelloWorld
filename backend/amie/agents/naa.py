# amie/agents/naa.py
# Novelty Assessment Agent (clean ref pipeline)
# Author: Harry
# 2025-10-03

import json
import time
import re
import requests
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

from google import genai
from google.genai import types
from langchain_core.runnables import RunnableLambda
from ..state import GraphState

# ---------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------
MODEL_TEXT_DEFAULT = "gemini-2.0-flash-lite-001"
CROSSREF_BASE = "https://api.crossref.org"
OPENALEX_BASE = "https://api.openalex.org"
MAX_OPENALEX_BATCH = 50
OPENALEX_PAGE_SIZE = 200

# ---------------------------------------------------------------------
# Utils
# ---------------------------------------------------------------------
def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d-%H-%M-%S")

def _normalize_title(t: str) -> str:
    return re.sub(r"\s+", " ", (t or "").strip().lower())

def _http_get(url: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    print(f"[DEBUG] GET {url} params={params}")
    r = requests.get(url, params=params or {}, timeout=(6, 18))
    r.raise_for_status()
    try:
        return r.json()
    except Exception:
        return {}

def call_llm_json_with_parts(client: "genai.Client", model: str, tag: str,
                             parts: List[Any], prompt_text: str,
                             schema: Dict[str, Any]) -> Any:
    print("\n" + "=" * 70)
    print(f"LLM INPUT [{tag}]")
    print(prompt_text)
    print("=" * 70, flush=True)

    resp = client.models.generate_content(
        model=model,
        contents=parts + [prompt_text],
        config=genai.types.GenerateContentConfig(
            response_schema=schema,
            response_mime_type="application/json"
        ),
    )
    text = getattr(resp, "text", "") or ""
    try:
        data = json.loads(text)
        print(f"[DEBUG] LLM OUTPUT [{tag}] keys={list(data) if isinstance(data, dict) else type(data)}")
        return data
    except Exception:
        print(f"[DEBUG] LLM OUTPUT [{tag}] raw={text[:200]}")
        raise RuntimeError(f"{tag}: non-JSON response")

# ---------------------------------------------------------------------
# Crossref
# ---------------------------------------------------------------------
def _crossref_lookup_bibliographic(cite_str: str, mailto: Optional[str]) -> Dict[str, Any]:
    if not cite_str.strip():
        return {}
    params = {"query.bibliographic": cite_str, "rows": 1}
    if mailto:
        params["mailto"] = mailto
    print(f"[DEBUG] Crossref query: {cite_str[:80]}...")
    js = _http_get(f"{CROSSREF_BASE}/works", params=params)
    items = js.get("message", {}).get("items") or []
    if not items:
        return {}
    it = items[0]
    doi = (it.get("DOI") or "").strip()
    title = (it.get("title") or [""])[0]
    url = (it.get("URL") or "").strip()
    pdf_url = ""
    for link in it.get("link", []):
        if link.get("content-type") == "application/pdf":
            pdf_url = (link.get("URL") or "").strip()
            break
    return {"doi": doi, "title": title, "url": url, "pdf_url": pdf_url}

# ---------------------------------------------------------------------
# OpenAlex
# ---------------------------------------------------------------------
def _chunk(lst: List[str], n: int) -> List[List[str]]:
    return [lst[i:i+n] for i in range(0, len(lst), n)]

def _openalex_get_works_by_dois(dois: List[str], mailto: Optional[str]) -> List[Dict[str, Any]]:
    if not dois:
        return []
    out = []
    for group in _chunk([d for d in dois if d], MAX_OPENALEX_BATCH):
        filt = "doi:" + "|".join(group)
        params = {"filter": filt, "per_page": len(group)}
        if mailto:
            params["mailto"] = mailto
        js = _http_get(f"{OPENALEX_BASE}/works", params=params)
        results = js.get("results") or []
        print(f"[DEBUG] OpenAlex batch {len(group)} → {len(results)}")
        for w in results:
            doi_url = (w.get("doi") or "").replace("https://doi.org/", "")
            best_oa = w.get("best_oa_location") or {}
            out.append({
                "title": w.get("title") or "",
                "doi": doi_url,
                "url": w.get("primary_location", {}).get("landing_page_url") or (f"https://doi.org/{doi_url}" if doi_url else ""),
                "pdf_url": best_oa.get("pdf_url") or "",
                "year": str(w.get("publication_year") or ""),
                "openalex_id": w.get("id") or ""
            })
        time.sleep(0.15)
    return out

def _openalex_list_all_cited_by(oaid: str, mailto: Optional[str]) -> List[Dict[str, Any]]:
    if not oaid:
        return []
    params = {"per_page": OPENALEX_PAGE_SIZE, "cursor": "*"}
    if mailto:
        params["mailto"] = mailto
    out, page = [], 0
    while True:
        js = _http_get(f"{OPENALEX_BASE}/works/{oaid}/cited-by", params=params)
        results = js.get("results") or []
        next_cursor = js.get("meta", {}).get("next_cursor")
        page += 1
        print(f"[DEBUG] cited-by page {page}: {len(results)} items (oaid={oaid})")
        for r in results:
            w = r.get("citing_work") or {}
            out.append({
                "title": w.get("title") or "",
                "url": w.get("primary_location", {}).get("landing_page_url") or "",
                "openalex_id": w.get("id") or "",
                "year": str(w.get("publication_year") or ""),
            })
        if not next_cursor:
            break
        params["cursor"] = next_cursor
        time.sleep(0.12)
    print(f"[DEBUG] cited-by TOTAL for {oaid}: {len(out)}")
    return out

# ---------------------------------------------------------------------
# Main NAA node
# ---------------------------------------------------------------------
def naa_node(state: GraphState, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    print("[DEBUG] Starting NAA node...")

    if state.get("runtime", {}).get("idca", {}).get("status") != "FINISHED":
        return {"artifacts": {"naa": {}}, "runtime": {"naa": {"status": "FINISHED"}}, "message": "Upstream not finished"}

    tar_gcs_uri = state.get("artifacts", {}).get("idca", {}).get("doc_gcs_uri")
    if not tar_gcs_uri:
        raise RuntimeError("No invention PDF found (idca.doc_gcs_uri).")

    cfg = (config or {}).get("configurable", {})
    client: "genai.Client" = cfg["genai_client"]
    model_name = cfg.get("model_name", MODEL_TEXT_DEFAULT)
    polite_email: Optional[str] = cfg.get("mailto") or "zhanhaoc@oregonstate.edu"

    # Step 1: Extract reference list
    prompt_refs = (
        "Analyze the paper's main content and extract its reference list. "
        "Rank references by contribution as baselines or relevance. "
        "Return a JSON array of 30 strings in descending importance."
    )
    schema_refs = {"type": "array", "items": {"type": "string"}}
    refs_list = call_llm_json_with_parts(
        client=client, model=model_name, tag="REFS",
        parts=[types.Part.from_uri(file_uri=tar_gcs_uri, mime_type="application/pdf")],
        prompt_text=prompt_refs, schema=schema_refs
    )
    references = [r for r in refs_list if isinstance(r, str) and r.strip()]
    print(f"[DEBUG] Got {len(references)} references")

    # Step 2: Crossref lookup
    crossref_hits = [_crossref_lookup_bibliographic(r, polite_email) for r in references]
    print(f"[DEBUG] Crossref resolved {sum(1 for h in crossref_hits if h.get('doi'))}/{len(crossref_hits)} DOIs")

    # Step 3: OpenAlex by DOIs
    doi_list = [h["doi"] for h in crossref_hits if h.get("doi")]
    works = _openalex_get_works_by_dois(doi_list, polite_email)
    seen, uniq = set(), []
    for w in works:
        key = _normalize_title(w["title"])
        if key and key not in seen:
            seen.add(key)
            uniq.append(w)
    works = uniq
    print(f"[DEBUG] Resolved unique refs: {len(works)}")

    # Step 4: Top-2 cited-by
    doi_to_work = {w["doi"]: w for w in works if w.get("doi")}
    top2 = []
    for h in crossref_hits:
        if len(top2) >= 2: break
        doi = h.get("doi")
        if doi and doi in doi_to_work:
            top2.append(doi_to_work[doi])
    print(f"[DEBUG] Top-2 selected: {len(top2)}")

    top2_cited_by = []
    for idx, w in enumerate(top2, 1):
        print(f"[DEBUG] Collecting cited-by for TOP{idx}: {w['title']}")
        cited = _openalex_list_all_cited_by(w["openalex_id"], polite_email)
        top2_cited_by.append({"reference_title": w["title"], "cited_by": cited})

    # Final assembly
    naa_art = {
        "core_subject": "",
        "reference_urls": works,
        "top2_cited_by": top2_cited_by,
        "generated_at": _now_iso()
    }

    return {
        "artifacts": {"naa": naa_art},
        "runtime": {"naa": {"status": "FINISHED"}},
        "message": "NAA refs + top2 cited-by completed"
    }

NOVELTY_A = RunnableLambda(naa_node)
