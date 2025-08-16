from __future__ import annotations
from typing import Dict, Any
from fastapi import APIRouter
from pydantic import BaseModel

from ...composite_agents.test_graph import TestGraphComposite

router = APIRouter(prefix="/composites/test-graph", tags=["composites"])

# Stateless is fine: create per-request or cache a singleton.
# Here we keep it simple and build per-call; swap to a module-level singleton if needed.
# TODO: globl stat management
# * since now is just local state for each request
class InvokeBody(BaseModel):
    state: Dict[str, Any] = {}

@router.post("/invoke")
def invoke_test_graph(body: InvokeBody) -> Dict[str, Any]:
    comp = TestGraphComposite()
    return comp.invoke(body.state)
