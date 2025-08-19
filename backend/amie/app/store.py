# amie/app/store.py
from __future__ import annotations
from typing import Dict, Any
from asyncio import Lock
from copy import deepcopy

class InMemoryStore:
    def __init__(self):
        self._data: Dict[str, Dict[str, Any]] = {}
        self._lock = Lock()

    async def save_state(self, request_id: str, state: Dict[str, Any]) -> None:
        async with self._lock:
            self._data[request_id] = deepcopy(state)

    async def update_state(self, request_id: str, patch: Dict[str, Any]) -> None:
        async with self._lock:
            base = self._data.get(request_id, {})
            base.update(patch)
            self._data[request_id] = deepcopy(base)

    async def get_state(self, request_id: str) -> Dict[str, Any]:
        async with self._lock:
            return deepcopy(self._data.get(request_id, {}))
