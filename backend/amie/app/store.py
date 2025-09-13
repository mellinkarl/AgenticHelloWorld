# amie/app/store.py
from __future__ import annotations
from typing import Dict, Any
from asyncio import Lock
from copy import deepcopy
from ..state import GraphState
class InMemoryStore:
    def __init__(self):
        self._data: Dict[str, GraphState] = {}
        self._lock = Lock()

    async def save_state(self, request_id: str, state: GraphState) -> None:
        async with self._lock:
            self._data[request_id] = deepcopy(state)

    async def update_state(self, request_id: str, patch: Dict[str, Any]) -> None:
        async with self._lock:
            base = self._data.get(request_id, GraphState())
            base.update(patch)
            self._data[request_id] = deepcopy(base)

    async def get_state(self, request_id: str) -> GraphState:
        async with self._lock:
            return deepcopy(self._data.get(request_id, GraphState()))