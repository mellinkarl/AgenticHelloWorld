'''
cmd: 
uvicorn src.app.main:app --reload

# Call LLMRunnerAgent (synchronous)
curl -X POST localhost:8000/agents/LLMRunnerAgent/invoke \
  -H 'content-type: application/json' \
  -d '{"state":{"user_input":"Say exactly: OK."},"async_mode":false}'

# Call PythonToolAgent (asynchronous), returns today's date
curl -X POST localhost:8000/agents/python-tool/invoke \
  -H 'content-type: application/json' \
  -d '{"state":{},"args":{"tool_name":"date.today","output_key":"today"},"async_mode":true}'

Example response format:

json
{
  "agent": "LLMRunnerAgent",       // The agent that was invoked
  "ms": 123,                       // Execution time in milliseconds
  "state_in": {                    // Original input state
    "user_input": "Say exactly: OK."
  },
  "state_out": {                   // Agent's output state
    "draft": "OK."
  }
}


# test-graph
curl -X POST localhost:8000/composites/test-graph/invoke \
  -H 'content-type: application/json' \
  -d '{"state":{"user_input":"demo"}}'



'''
from __future__ import annotations
from fastapi import FastAPI, Request
from uuid import uuid4

from ..config import Config, init_logging, get_logger
from ..tools.registry import registry
from ..tools.date_tool import get_today_iso
from ..core.context import set_request_id
from .routes.agents import router as agents_router

from .routes.test_graph import router as test_graph_router  # add this file (see below)

log = get_logger(__name__)

def create_app() -> FastAPI:
    # Config + JSON logging
    cfg = Config.load()
    init_logging(cfg)

    # Tool registry (safe to call multiple times; last one wins)
    # TODO: maybe we should register on startup
    registry.register("date.today", get_today_iso)
    registry.register("string.mark_double", lambda s: f"double::{s}")

    app = FastAPI(title="Agent Backend", version="0.1.0")

    # Routers
    app.include_router(agents_router)
    app.include_router(test_graph_router)  # ⬅️ expose the composite

    @app.middleware("http")
    async def request_id_middleware(request: Request, call_next):
        rid = request.headers.get("x-request-id") or str(uuid4())
        set_request_id(rid)
        resp = await call_next(request)
        resp.headers["x-request-id"] = rid
        return resp

    @app.get("/healthz")
    def healthz():
        return {"status": "ok"}

    log.info("FastAPI app initialized")
    return app

app = create_app()
