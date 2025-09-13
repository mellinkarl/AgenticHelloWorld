# amie/agents/ia.py
# Ingestion Agent (IA) with local temp-file caching
# Author: Harry + update by assistant per requested behavior
# 2025-09-03
# amie/agents/ia.py
# Ingestion Agent (IA) with local temp-file caching
# Author: Harry + update by assistant per requested behavior
# 2025-09-03

from __future__ import annotations

import os
import io
import base64
import tempfile
from datetime import datetime as _dt
from typing import Dict, Any, Tuple, Optional, List

from google.cloud import storage
from langchain_core.runnables import RunnableLambda

from ..state import GraphState

# --------------------------- utils: parse gs:// and download ---------------------------

def _parse_gs_url(uri: str) -> Tuple[str, str]:
    if not isinstance(uri, str) or not uri.startswith("gs://"):
        raise ValueError("doc_uri must start with 'gs://'")
    without_scheme = uri[5:]
    parts = without_scheme.split("/", 1)
    if len(parts) != 2 or not parts[0] or not parts[1]:
        raise ValueError("Invalid GCS URI format")
    return parts[0], parts[1]


def _download_gcs(uri: str) -> Dict[str, Any]:
    bucket_name, object_name = _parse_gs_url(uri)
    client = storage.Client()
    blob = client.bucket(bucket_name).blob(object_name)

    try:
        blob.reload()
    except Exception:
        pass  # non-fatal

    try:
        data = blob.download_as_bytes(timeout=60)
        ok = True
        err = None
    except Exception as e:
        data = None
        ok = False
        err = f"download failed: {e}"

    updated_iso: Optional[str] = None
    try:
        updated_obj = getattr(blob, "updated", None)
        if isinstance(updated_obj, _dt):
            updated_iso = updated_obj.isoformat()
    except Exception:
        updated_iso = None

    try:
        size_fallback = int(getattr(blob, "size", 0) or 0)
    except Exception:
        size_fallback = 0

    return {
        "ok": ok,
        "error": err,
        "bucket": bucket_name,
        "object": object_name,
        "size": len(data) if data is not None else size_fallback,
        "content_type": getattr(blob, "content_type", None),
        "updated_iso": updated_iso,
        "data": data,
    }


# --------------------------- utils: PDF probe (PyMuPDF) ---------------------------

def _assert_pdf_or_raise(pdf_bytes: bytes) -> None:
    """
    Validate if PyMuPDF can open as a PDF. Raises if not.
    """
    import pymupdf  # lazy import
    doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    try:
        _ = doc.page_count
    finally:
        doc.close()


# --------------------------- helpers: extension, local path ---------------------------

def _ext_from_ct_or_name(ct: Optional[str], name: Optional[str]) -> str:
    ct = (ct or "").lower()
    name_l = (name or "").lower()

    if name_l.endswith(".pdf") or ct == "application/pdf":
        return ".pdf"
    for suf in (".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".tiff", ".tif"):
        if name_l.endswith(suf):
            return suf
    if ct.startswith("image/"):
        return ".img"
    return ".bin"


def _compose_local_path(request_id: str, ext: str) -> str:
    """
    Build a container-local path for the temp copy.
    Root can be overridden by env AMIE_TMP_DIR; defaults to OS temp dir.
    Path layout: <tmp>/amie/<request_id>/document<ext>
    """
    root = os.environ.get("AMIE_TMP_DIR", tempfile.gettempdir())
    local_dir = os.path.join(root, "amie", request_id)
    os.makedirs(local_dir, exist_ok=True)
    return os.path.join(local_dir, f"document{ext}")

# --------------------------- formal IA with local temp-file caching ---------------------------

def ia_node(state: GraphState) -> Dict[str, Any]:
    """
    Behavior:
      1) Read GCS URI from state (prefer `doc_gcs_uri`, fall back to `doc_uri`).
      2) Download the object bytes from GCS.
      3) If it's a PDF (by suffix or content-type), validate with PyMuPDF.
      4) Save the bytes into a container-local temp path (/tmp or $AMIE_TMP_DIR).
      5) Return a patch WITHOUT storing logs in state. Logs are only printed.
         On failure, return minimal fields plus a `message`.
    """
    request_id = str(state.get("request_id") or "")
    uri = state.get("doc_gcs_uri") or state.get("doc_local_uri") or ""

    print(f"[IA][0] start | request_id={request_id or 'n/a'}")
    print(f"[IA][1] input uri={uri or 'None'}")

    # Guard: require gs://
    if not (isinstance(uri, str) and uri.startswith("gs://")):
        msg = "IA: expected `doc_gcs_uri` starting with gs://"
        print(f"[IA][ERR] {msg}")
        return {
            "runtime": {"ia": {"status": "FAILED", "route": []}},
            "artifacts": {"ia": {"doc_local_uri": uri, "storage": "unknown", "ok": False}},
            "internals": {"ia": {"reason": "non-gcs-uri"}},
            "message": msg,
        }

    # Download
    try:
        print("[IA][2] downloading from GCS …")
        dl = _download_gcs(uri)
        print(f"[IA][2] download ok={dl.get('ok')} size={dl.get('size')} ct={dl.get('content_type') or 'n/a'}")
    except Exception as e:
        msg = f"IA: exception during download: {e}"
        print(f"[IA][ERR] {msg}")
        return {
            "runtime": {"ia": {"status": "FAILED", "route": []}},
            "artifacts": {"ia": {"doc_local_uri": uri, "storage": "gcs", "ok": False}},
            "internals": {"ia": {"reason": "download-exception"}},
            "message": msg,
        }

    if not dl["ok"] or not isinstance(dl.get("data"), (bytes, bytearray)):
        err = dl.get("error")
        msg = f"IA: download failed: {err}"
        print(f"[IA][ERR] {msg}")
        return {
            "runtime": {"ia": {"status": "FAILED", "route": []}},
            "artifacts": {"ia": {"doc_local_uri": uri, "storage": "gcs", "ok": False}},
            "internals": {"ia": {"reason": "download-failed"}},
            "message": msg,
        }

    # Validate PDF if applicable
    obj_name = dl.get("object") or ""
    ct = dl.get("content_type") or ""
    ext = _ext_from_ct_or_name(ct, obj_name)
    data_bytes: bytes = bytes(dl["data"])

    print(f"[IA][3] detect ext={ext} ct={ct or 'n/a'} name={obj_name or 'n/a'}")
    if ext == ".pdf" or ct.lower() == "application/pdf" or obj_name.lower().endswith(".pdf"):
        print("[IA][3] PDF detected, validating with PyMuPDF …")
        try:
            _assert_pdf_or_raise(data_bytes)
            print("[IA][3] PDF validation: OK")
        except Exception:
            msg = "IA: file downloaded but not a valid PDF (PyMuPDF open failed)"
            print(f"[IA][ERR] {msg}")
            return {
                "runtime": {"ia": {"status": "FAILED", "route": []}},
                "artifacts": {"ia": {"doc_local_uri": uri, "storage": "gcs", "ok": False}},
                "internals": {"ia": {"reason": "pdf-validate-failed"}},
                "message": msg,
            }

    # Persist to local temp storage
    try:
        print("[IA][4] writing local temp file …")
        local_path = _compose_local_path(request_id or "unknown", ext)
        with open(local_path, "wb") as f:
            f.write(data_bytes)
        file_uri = f"file://{os.path.abspath(local_path)}"
        print(f"[IA][4] wrote to {file_uri}")
    except Exception as e:
        msg = f"IA: failed to write local temp file: {e}"
        print(f"[IA][ERR] {msg}")
        return {
            "runtime": {"ia": {"status": "FAILED", "route": []}},
            "artifacts": {"ia": {"doc_local_uri": uri, "storage": "gcs", "ok": False}},
            "internals": {"ia": {"reason": "local-write-failed"}},
            "message": msg,
        }

    # Success
    art: Dict[str, Any] = {
        "ok": True,
        "doc_uri": uri,
        "storage": "gcs",
        "bucket": dl.get("bucket"),
        "object": obj_name,
        "size": dl.get("size"),
        "content_type": ct,
        "updated_iso": dl.get("updated_iso"),
        "doc_local_uri": file_uri,
        "is_pdf": ext == ".pdf",
    }
    internals: Dict[str, Any] = {
        "used_client": "google-cloud-storage",
        "cleanup_hint": os.path.dirname(local_path),
    }

    print(f"[IA][5] success | local_uri={file_uri}")
    print(f"[IA][5] summary | gcs=gs://{dl.get('bucket')}/{obj_name} size={dl.get('size')} ct={ct or 'n/a'} updated={dl.get('updated_iso') or 'n/a'}")

    return {
        "runtime": {"ia": {"status": "FINISHED", "route": []}},
        "artifacts": {"ia": art},
        "internals": {"ia": internals},
        "doc_local_uri": file_uri,
    }

# --------------------------- dummy no-op node (kept for reference) ---------------------------

def ia_node_dummy(state: GraphState, config=None) -> Dict[str, Any]:
    """
    Dummy IA: prints logs only, does not save logs into state.
    """
    request_id = str(state.get("request_id") or "dummy-request")
    uri = state.get("doc_gcs_uri", "") or state.get("doc_local_uri", "") or "gs://dummy-bucket/dummy.pdf"
    storage_kind = "gcs" if isinstance(uri, str) and uri.startswith("gs://") else "local"

    local_path = f"/tmp/amie/{request_id}/document.pdf"
    file_uri = f"file://{local_path}"

    print(f"[IA][DUMMY] start | request_id={request_id}")
    print(f"[IA][DUMMY] fixed uri={uri}")
    print(f"[IA][DUMMY] using storage={storage_kind}, local_uri={file_uri}")
    print("[IA][DUMMY] done")

    art = {
        "ok": True,
        "doc_uri": uri,
        "storage": storage_kind,
        "bucket": "aime-hello-world-amie-uswest1",
        "object": "amie/tmp/fixed_dummy.pdf",
        "size": 123456,
        "content_type": "application/pdf",
        "updated_iso": "2025-09-12T00:00:00Z",
        "doc_local_uri": file_uri,
        "is_pdf": True,
    }

    cache = {
        "normalized_uri": uri,
        "used_client": "dummy",
        "cleanup_hint": f"/tmp/amie/{request_id}",
    }

    return {
        "runtime": {"ia": {"status": "FINISHED", "route": []}},
        "artifacts": {"ia": art},
        "internals": {"ia": cache},
        "doc_local_uri": file_uri,
    }


# --------------------------- default export ---------------------------

INGESTION = RunnableLambda(ia_node_dummy)
