# amie/app/main.py
from __future__ import annotations

from fastapi import FastAPI, HTTPException, BackgroundTasks
from uuid import uuid4
from datetime import datetime, timezone

from ..state import GraphState
from ..graph import build_graph
from .store import InMemoryStore
from ..state import GraphState, default_runtime_block
from ..state import frontend_view

app = FastAPI(title="AMIE API")
app.state.graph = build_graph()
app.state.store = InMemoryStore()

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

@app.post("/invoke")
async def invoke(payload: dict, background_tasks: BackgroundTasks):
    gcs_url = payload.get("gcs_url")
    metadata = payload.get("metadata", {}) or {}
    if not gcs_url:
        raise HTTPException(status_code=400, detail="Missing gcs_url")

    request_id = str(uuid4())

    init: GraphState = {
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
        "runtime": default_runtime_block(),   # <-- NEW
        "artifacts": {},                      # agent-scoped + report
        "internals": {"ia": {}, "idca": {}, "naa": {}, "aa": {}},
        "errors": [],
        "logs": [],
    }
    await app.state.store.save_state(request_id, init)

    async def run_graph():
        # Mark RUNNING
        await app.state.store.update_state(request_id, {"status": "RUNNING", "updated_at": now_iso()})
        try:
            # Feed the initial state; thread_id = request_id
            result = await app.state.graph.ainvoke(
                init,
                config={"configurable": {"thread_id": request_id}}
            )
            # The compiled graph returns the merged state. Persist + mark FINISHED.
            result["status"] = "FINISHED"
            result["updated_at"] = now_iso()
            await app.state.store.save_state(request_id, result)
        except Exception as e:
            # On failure, capture error and mark FAILED.
            failed = await app.state.store.get_state(request_id)
            (failed.setdefault("errors", [])).append(str(e))
            failed["status"] = "FAILED"
            failed["updated_at"] = now_iso()
            await app.state.store.save_state(request_id, failed)

    # Return the request_id immediately; run graph in background.
    background_tasks.add_task(run_graph)
    return {"request_id": request_id}

@app.get("/state/{request_id}")
async def get_state(request_id: str):
    state = await app.state.store.get_state(request_id)
    if not state:
        raise HTTPException(status_code=404, detail="Unknown request_id")
    return frontend_view(state)   # <-- expose only the final report + top-level status/ids

@app.get("/debug_state/{request_id}")
async def debug_state(request_id: str):
    state = await app.state.store.get_state(request_id)
    if not state:
        raise HTTPException(status_code=404, detail="Unknown request_id")
    return state