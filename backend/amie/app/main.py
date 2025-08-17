# amie/app/main.py
# Author: Harry
# Date: 2025-08-16
# FastAPI entrypoint for AMIE system

# ====== amie/app/main.py ======
from fastapi import FastAPI, HTTPException
from uuid import uuid4
import aiosqlite
from contextlib import asynccontextmanager

from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from amie.graph import build_graph
from amie.state import GraphState



graph:  None   # will be initialized in lifespan


# ====== Lifespan: startup & shutdown ======
@asynccontextmanager
async def lifespan(app: FastAPI):
    conn = await aiosqlite.connect("checkpoint.db")
    checkpointer = AsyncSqliteSaver(conn)
    app.state.graph = build_graph(checkpointer=checkpointer)
    yield
    await conn.close()


# ====== FastAPI App ======
app = FastAPI(lifespan=lifespan)


# ====== POST /invoke ======
@app.post("/invoke")
async def invoke(payload: dict):
    gcs_url = payload.get("gcs_url")
    metadata = payload.get("metadata", {})
    if not gcs_url:
        raise HTTPException(status_code=400, detail="Missing gcs_url")

    request_id = str(uuid4())
    state: GraphState = {
        "request_id": request_id,
        "doc_uri": gcs_url,
        "metadata": metadata,
        "logs": [],
        "errors": [],
    }

    await app.state.graph.ainvoke(state, config={"configurable": {"thread_id": request_id}})
    return {"request_id": request_id}


# ====== GET /state/{request_id} ======
@app.get("/state/{request_id}")
async def get_state(request_id: str):
    state = await app.state.graph.aget_state(
        config={"configurable": {"thread_id": request_id}}
    )
    if not state:
        raise HTTPException(status_code=404, detail="Request not found")
    return state

