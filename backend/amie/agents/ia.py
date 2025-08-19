# amie/agents/ia.py
# Ingestion Agent (IA)
# Author: Harry (implementation completed per IA-only scope)
# 2025-08-18

import json
from typing import Dict, Any
from langchain_core.runnables import RunnableLambda
from ..state import GraphState

def ia_node(state: GraphState) -> Dict[str, Any]:
    """
    Ingestion Agent (dummy):
    - Normalizes `doc_uri` into a canonical reference (no-op here).
    - Emits a small ingestion artifact (storage guessed as local|gcs).
    - Stores a tiny internal cache for downstream agents to read.
    """
    uri = state.get("doc_uri", "")
    storage = "gcs" if uri.startswith("gs://") else "local"

    ingestion_art = {
        "doc_uri": uri,
        "storage": storage,
        # In real IA, you'd also compute checksum/mime/size and possibly a signed URL.
        # "checksum": "sha256:...",
        # "mime": "application/pdf",
    }
    ia_cache = {
        "normalized_uri": uri,
        "note": "dummy IA completed",
    }

    return {
        "runtime":   {"ia": {"status": "FINISHED", "route": []}},
        "artifacts": {"ia": ingestion_art},
        "internals": {"ia": ia_cache},
        "logs":      ["IA: normalized input (dummy)."],
}

# Export as a LangGraph Runnable node
INGESTION = RunnableLambda(ia_node)
