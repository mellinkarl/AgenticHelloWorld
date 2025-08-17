# amie/state.py
# AMIE graph state
# Author: Harry
# 2025-08-16

# TODO: those need to change & refine
from __future__ import annotations

import operator
from typing import Any, Dict, List, Optional
from typing_extensions import Annotated, TypedDict
from langchain.schema import Document
from langchain_core.messages import AnyMessage


class GraphState(TypedDict, total=False):

    # === LangGraph/LangChain: conversational memory & RAG support ===
    # Chat conversation buffer; appended across nodes (demo-style memory).
    messages: Annotated[List[AnyMessage], operator.add]

    # Retrieved documents for RAG or grading steps.
    documents: List[Document]

    # Last LLM output (string or message object), if any.
    generation: Any

    # Retry counter for generation/validation loops.
    attempted_generations: int

    # === AMIE: invocation basics (seeded by API layer) ===
    # Unique ID for the run; also used as LangGraph thread_id for checkpointing.
    request_id: str

    # Input document location (gs://... or a signed URL).
    doc_uri: str

    # Arbitrary user-supplied metadata (IDs, flags, configs, etc.).
    # Put large/ephemeral, agent-specific blobs under a namespaced key, e.g.:
    #   metadata["ingestion"] = {...}, metadata["idca_hints"] = {...}
    metadata: Dict[str, Any]

    # === AMIE: intermediate artifacts ===
    # Parsed fulltext of the manuscript (None if not available or not parsed).
    manuscript_text: Optional[str]

    # Invention Detection & Classification result:
    #   { "status": "present" | "absent" | "implied", "summary": str, "fields": list, "reasoning": str }
    idca: Dict[str, Any]

    # Novelty Assessment result:
    #   { "novel": bool | "undetermined", "matches": list, "reasoning": str }
    novelty: Dict[str, Any]

    # === AMIE: final artifact ===
    # Deterministic, structured JSON report produced by the aggregation node.
    report: Dict[str, Any]

    # === Diagnostics (append-only channels; MUST use reducers) ===
    # Human-readable error notes accumulated across nodes.
    errors: Annotated[List[str], operator.add]

    # Human-readable progress and trace messages accumulated across nodes.
    logs: Annotated[List[str], operator.add]

