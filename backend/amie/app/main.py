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

if not GCS_BUCKET:
    raise RuntimeError("Env GCS_BUCKET is required")

# Global Genai, GCS client and bucket handle (initialized in lifespan)
genai_client: genai.Client | None = None
storage_client: storage.Client | None = None
bucket: storage.Bucket | None = None



def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_prefix(p: str) -> str:
    """Normalize a GCS prefix to always end with '/' if non-empty."""
    p = (p or "").lstrip("/")
    if p and not p.endswith("/"):
        p += "/"
    return p


def _full_key_for_new_pdf() -> str:
    """Generate a new object key under the configured prefix with random UUID filename."""
    prefix = _normalize_prefix(GCS_PREFIX)
    return f"{prefix}{uuid4().hex}.pdf"


def _ensure_14d_delete_lifecycle(bkt: storage.Bucket, prefix: str, days: int = 14) -> None:
    """
    Ensure a lifecycle rule exists that deletes PDFs under `prefix` after `days`.
    Uses the public helper `add_lifecycle_delete_rule` (no direct list append).
    """
    from typing import Any

    pref = _normalize_prefix(prefix)

    # Materialize current rules to a list of dicts for comparison
    # (Pylance may type this as a Generator → don't mutate in place).
    current_rules: list[dict[str, Any]] = list(bkt.lifecycle_rules or [])

    desired = {
        "action": {"type": "Delete"},
        "condition": {
            "age": days,
            "matchesPrefix": [pref] if pref else [],
            "matchesSuffix": [".pdf"],
        },
    }

    def _norm(rule: dict[str, Any]) -> dict[str, Any]:
        # Keep only fields we care about for equality
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
        # Add via helper, then patch
        bkt.add_lifecycle_delete_rule(
            age=days,
            matches_prefix=[pref] if pref else None,
            matches_suffix=[".pdf"],
        )
        bkt.patch()

# --------- Lifespan handler (replaces @app.on_event("startup")) ---------
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    global genai_client, storage_client, bucket
    # Startup
    genai_client = genai.Client(vertexai=True, project=GC_PROJECT, location="us-west1")
    storage_client = storage.Client()
    bucket = storage_client.bucket(GCS_BUCKET)

    try:
        _ensure_14d_delete_lifecycle(bucket, GCS_PREFIX, days=14)
    except Exception as e:
        # Non-fatal: just warn
        print(f"[WARN] ensure lifecycle failed: {e}")

    yield  # Application runs

    # Shutdown (nothing special; keep for symmetry)
    genai_client = None
    storage_client = None
    bucket = None

# Attach lifespan to the app
app.router.lifespan_context = lifespan

# ----------------- Original AMIE logic -----------------

@app.post("/invoke")
async def invoke(payload: dict, background_tasks: BackgroundTasks):
    gcs_url = payload.get("gcs_url")
    metadata = payload.get("metadata", {}) or {}
    if not gcs_url:
        raise HTTPException(status_code=400, detail="Missing gcs_url")

    request_id = str(uuid4())

    init: GraphState = {
        "genai_client": genai_client,
        "request_id": request_id,
        "doc_uri": gcs_url,
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


# ----------------- PDF upload to GCS -----------------

@app.post("/upload-pdf")
async def upload_pdf(
    file: UploadFile = File(..., description="PDF file (multipart/form-data, field: file)"),
    return_signed_url: bool = Query(True, description="Return temporary signed HTTPS URL"),
    signed_url_ttl_seconds: int = Query(
        None, ge=60, le=7 * 24 * 3600, description="Override default signed URL TTL"
    ),
):
    """
    Accepts a PDF, uploads to GCS under the configured prefix, and returns gs:// URL
    plus an optional signed HTTPS URL. Lifecycle is enforced on startup:
    matching prefix + .pdf suffix are deleted automatically after 14 days.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="Missing filename")

    content_type = (file.content_type or "").lower()
    name_lc = file.filename.lower()

    if "pdf" not in content_type and not name_lc.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are allowed")

    key = _full_key_for_new_pdf()
    assert bucket is not None, "GCS bucket is not initialized"
    blob = bucket.blob(key)

    guessed = mimetypes.guess_type(key)[0] or "application/pdf"
    ct = "application/pdf" if "pdf" in content_type else guessed

    try:
        blob.upload_from_file(file.file, content_type=ct, rewind=True, timeout=60, num_retries=3)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {e}")

    gs_url = f"gs://{GCS_BUCKET}/{key}"

    result: dict[str, Any] = {
        "bucket": GCS_BUCKET,
        "object": key,
        "gs_url": gs_url,
        "content_type": ct,
        "size": blob.size,
        "lifecycle": {
            "delete_after_days": 14,
            "matches_prefix": _normalize_prefix(GCS_PREFIX),
            "matches_suffix": ".pdf",
        },
    }

    if return_signed_url:
        ttl = signed_url_ttl_seconds or SIGNED_URL_TTL_SECONDS
        try:
            url = blob.generate_signed_url(expiration=timedelta(seconds=ttl), method="GET")
            result["signed_url"] = url
            result["signed_url_expires_in"] = ttl
        except Exception as e:
            result["signed_url_error"] = f"Signed URL generation failed: {e}"

    result["suggested_invoke_payload"] = {"gcs_url": gs_url, "metadata": {"source": "upload-pdf"}}

    return JSONResponse(result)


@app.post("/get-upload-url")
async def get_upload_url_todo():
    """
    TODO(amie): Frontend direct-to-GCS via signed URL.
    Design:
      - Request: { "filename": str, "content_type": str, "size"?: int, "sha256"?: str }
      - Response: { "upload_url": str, "gs_url": str, "headers_to_set": dict, "expires_in": int }
    Notes:
      - Use GCS signed URL (method=PUT, content_type bound, short TTL).
      - Frontend uploads directly to GCS, then calls /invoke with gs_url.
      - Keep /upload-pdf as backend-proxied fallback for small files/tests.
    """
    raise HTTPException(status_code=501, detail="Not implemented: direct signed upload URL")
