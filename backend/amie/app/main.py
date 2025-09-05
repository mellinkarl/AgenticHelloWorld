# amie/app/main.py
from __future__ import annotations

import os
import mimetypes
from uuid import uuid4
from datetime import datetime, timezone, timedelta
from typing import Any

from fastapi import FastAPI, HTTPException, BackgroundTasks, UploadFile, File, Query
from fastapi.responses import JSONResponse
from google import genai
from google.cloud import storage

from ..state import GraphState, default_runtime_block, frontend_view
from ..graph import build_graph
from .store import InMemoryStore

app = FastAPI(title="AMIE API")
app.state.graph = build_graph()
app.state.store = InMemoryStore()

# ---- GCS environment configuration ----
GC_PROJECT = os.environ.get("GC_PROJECT")  # required (Project ID of Google Cloud Project)
GCS_BUCKET = os.environ.get("GCS_BUCKET")  # required (Name of the bucket)
GCS_PREFIX = os.environ.get("GCS_PREFIX", "amie/pdf/")  # default prefix for uploaded PDFs
SIGNED_URL_TTL_SECONDS = int(os.environ.get("SIGNED_URL_TTL_SECONDS", "3600"))  # default: 1h
GCS_BUCKET = os.environ.get("GCS_BUCKET", "aime-hello-world-amie-uswest1")
GCS_PREFIX = os.environ.get("GCS_PREFIX", "amie/tmp/")
SIGNED_URL_TTL_SECONDS = int(os.environ.get("SIGNED_URL_TTL_SECONDS", str(7 * 24 * 3600)))

if not GCS_BUCKET:
    raise RuntimeError("Env GCS_BUCKET is required")

# Global Genai, GCS client and bucket handle (initialized in lifespan)
genai_client: genai.Client | None = None
# ---- Accepted types: PDF and images ----
ACCEPTED_SUFFIXES = [
    ".pdf", ".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".tiff", ".tif"
]
ACCEPTED_CT_EXACT = {"application/pdf"}
ACCEPTED_CT_PREFIXES = {"image/"}  # any image/*

# Global GCS client and bucket handle (initialized in lifespan)
storage_client: storage.Client | None = None
bucket: storage.Bucket | None = None



def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def _normalize_prefix(p: str) -> str:
    p = (p or "").lstrip("/")
    if p and not p.endswith("/"):
        p += "/"
    return p

def _ext_from_content_type(ct: str | None) -> str | None:
    if not ct:
        return None
    # Normalize jpg extension
    ext = mimetypes.guess_extension(ct) or None
    if ext in {".jpe"}:
        ext = ".jpg"
    return ext

def _is_accepted(filename: str | None, content_type: str | None) -> bool:
    name_lc = (filename or "").lower()
    ct = (content_type or "").lower()
    if any(name_lc.endswith(suf) for suf in ACCEPTED_SUFFIXES):
        return True
    if ct in ACCEPTED_CT_EXACT:
        return True
    if any(ct.startswith(pref) for pref in ACCEPTED_CT_PREFIXES):
        return True
    return False

def _choose_ext(filename: str | None, content_type: str | None) -> str:
    name_lc = (filename or "").lower()
    for suf in ACCEPTED_SUFFIXES:
        if name_lc.endswith(suf):
            return suf
    guessed = _ext_from_content_type(content_type)
    if guessed in ACCEPTED_SUFFIXES:
        return guessed
    # Fallback: default to .pdf if content_type declared as pdf, else .bin (should not happen due to gate)
    if (content_type or "").lower() in ACCEPTED_CT_EXACT:
        return ".pdf"
    return ".bin"

def _full_key_for_new_object(filename: str | None, content_type: str | None) -> str:
    prefix = _normalize_prefix(GCS_PREFIX)
    ext = _choose_ext(filename, content_type)
    return f"{prefix}{uuid4().hex}{ext}"

def _ensure_delete_lifecycle(bkt: storage.Bucket, prefix: str, days: int = 7, suffixes: list[str] | None = None) -> None:
    """
    Ensure a lifecycle rule exists that deletes objects under `prefix` with any of `suffixes` after `days`.
    """
    from typing import Any

    pref = _normalize_prefix(prefix)
    suffixes = suffixes or [".pdf"]

    current_rules: list[dict[str, Any]] = list(bkt.lifecycle_rules or [])

    desired = {
        "action": {"type": "Delete"},
        "condition": {
            "age": days,
            "matchesPrefix": [pref] if pref else [],
            "matchesSuffix": sorted(suffixes),
        },
    }

    def _norm(rule: dict[str, Any]) -> dict[str, Any]:
        action = rule.get("action", {})
        cond = rule.get("condition", {})
        return {
            "action": {"type": action.get("type")},
            "condition": {
                "age": cond.get("age"),
                "matchesPrefix": sorted(cond.get("matchesPrefix") or []),
                "matchesSuffix": sorted(cond.get("matchesSuffix") or []),
            },
        }

    exists = any(_norm(r) == _norm(desired) for r in current_rules)
    if not exists:
        bkt.add_lifecycle_delete_rule(
            age=days,
            matches_prefix=[pref] if pref else None,
            matches_suffix=list(suffixes),
        )
        bkt.patch()

# --------- Lifespan handler ---------
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    global genai_client, storage_client, bucket
    # Startup
    genai_client = genai.Client(vertexai=True, project=GC_PROJECT, location="us-west1")
    global storage_client, bucket
    storage_client = storage.Client()
    bucket = storage_client.bucket(GCS_BUCKET)

    try:
        # Align cleanup to 7 days so V4 signed URL can match it
        _ensure_delete_lifecycle(bucket, GCS_PREFIX, days=7, suffixes=ACCEPTED_SUFFIXES)
    except Exception as e:
        print(f"[WARN] ensure lifecycle failed: {e}")

    yield

    # Shutdown (nothing special; keep for symmetry)
    genai_client = None
    storage_client = None
    bucket = None

app.router.lifespan_context = lifespan

# ----------------- Original AMIE logic -----------------

@app.post("/invoke")
async def invoke(payload: dict, background_tasks: BackgroundTasks):
    doc_gcs_uri = payload.get("gcs_url")
    metadata = payload.get("metadata", {}) or {}
    if not doc_gcs_uri:
        raise HTTPException(status_code=400, detail="Missing gcs_url")

    request_id = str(uuid4())

    init: GraphState = {
        "genai_client": genai_client,
        "request_id": request_id,
        "doc_gcs_uri": doc_gcs_uri,
        "metadata": metadata,
        "status": "PENDING",
        "created_at": now_iso(),
        "updated_at": now_iso(),
        "messages": [],
        "documents": [],
        "generation": None,
        "attempted_generations": 0,
        "runtime": default_runtime_block(),
        "artifacts": {},
        "internals": {"ia": {}, "idca": {}, "naa": {}, "aa": {}},
        "errors": [],
        "logs": [],
    }
    await app.state.store.save_state(request_id, init)

    async def run_graph():
        await app.state.store.update_state(
            request_id, {"status": "RUNNING", "updated_at": now_iso()}
        )
        try:
            result = await app.state.graph.ainvoke(
                init, config={"configurable": {"thread_id": request_id}}
            )
            result["status"] = "FINISHED"
            result["updated_at"] = now_iso()
            await app.state.store.save_state(request_id, result)
        except Exception as e:
            failed = await app.state.store.get_state(request_id)
            (failed.setdefault("errors", [])).append(str(e))
            failed["status"] = "FAILED"
            failed["updated_at"] = now_iso()
            await app.state.store.save_state(request_id, failed)

    background_tasks.add_task(run_graph)
    return {"request_id": request_id}

@app.get("/state/{request_id}")
async def get_state(request_id: str):
    state = await app.state.store.get_state(request_id)
    if not state:
        raise HTTPException(status_code=404, detail="Unknown request_id")
    return frontend_view(state)

@app.get("/debug_state/{request_id}")
async def debug_state(request_id: str):
    state = await app.state.store.get_state(request_id)
    if not state:
        raise HTTPException(status_code=404, detail="Unknown request_id")
    return state

# ----------------- File upload to GCS (PDF or Image) -----------------

@app.post("/upload-file")
async def upload_file(
    file: UploadFile = File(..., description="File (PDF or Image). multipart/form-data, field: file"),
    return_signed_url: bool = Query(False, description="Return temporary signed HTTPS URL"),
    signed_url_ttl_seconds: int | None = Query(
        None, ge=60, le=7 * 24 * 3600, description="Override default signed URL TTL (max 7d)"
    ),
):
    """
    Accepts a file but only allows PDF and images.
    Uploads to GCS under the configured prefix and returns gs:// URL
    plus an optional signed HTTPS URL. Lifecycle deletes after 7 days
    for all accepted suffixes.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="Missing filename")

    if not _is_accepted(file.filename, file.content_type):
        raise HTTPException(status_code=400, detail="Only PDF and image files are allowed")

    key = _full_key_for_new_object(file.filename, file.content_type)
    assert bucket is not None, "GCS bucket is not initialized"
    blob = bucket.blob(key)

    # Content-Type: prefer client-declared if acceptable, else guess from key
    ct = (file.content_type or "").lower()
    if not (ct in ACCEPTED_CT_EXACT or any(ct.startswith(p) for p in ACCEPTED_CT_PREFIXES)):
        ct = mimetypes.guess_type(key)[0] or "application/octet-stream"

    try:
        blob.upload_from_file(file.file, content_type=ct, rewind=True, timeout=60, num_retries=3)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {e}")

    doc_gcs_uri = f"gs://{GCS_BUCKET}/{key}"

    result: dict[str, Any] = {
        "bucket": GCS_BUCKET,
        "object": key,
        "doc_gcs_uri": doc_gcs_uri,
        "content_type": ct,
        "size": blob.size,
        "lifecycle": {
            "delete_after_days": 7,
            "matches_prefix": _normalize_prefix(GCS_PREFIX),
            "matches_suffix": ACCEPTED_SUFFIXES,
        },
    }

    if return_signed_url:
        ttl = min(signed_url_ttl_seconds or SIGNED_URL_TTL_SECONDS, 7 * 24 * 3600)
        try:
            url = blob.generate_signed_url(
                expiration=timedelta(seconds=ttl),
                method="GET",
                version="v4",
            )
            result["signed_url"] = url
            result["signed_url_expires_in"] = ttl
        except Exception as e:
            result["signed_url_error"] = f"Signed URL generation failed: {e}"

    # minimal suggestion body for downstream /invoke usage
    result["suggested_invoke_payload"] = {
        "doc_gcs_uri": doc_gcs_uri,
        "metadata": {"source": "upload-file"}
    }

    return JSONResponse(result)

@app.post("/get-upload-url")
async def get_upload_url_todo():
    """
    TODO: direct-to-GCS via signed URL (PUT) for allowed types only.
    """
    raise HTTPException(status_code=501, detail="Not implemented: direct signed upload URL")
