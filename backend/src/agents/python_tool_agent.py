from __future__ import annotations
from typing import Mapping, Dict, Any, Callable, Optional

class PythonToolAgent:
    """
    Wrap a Python callable as an Agent.
    - func: Callable[..., Any]
    - output_key: where to store result in state
    - kwargs_from_state: mapping {param_name: state_key} to pass dynamic args
    """
    def __init__(
        self,
        func: Callable[..., Any],
        *,
        output_key: str,
        kwargs_from_state: Optional[Dict[str, str]] = None,
    ):
        self.func = func
        self.output_key = output_key
        self.kwargs_from_state = kwargs_from_state or {}

    def invoke(self, state: Mapping[str, Any]) -> Dict[str, Any]:
        kwargs = {param: state.get(src_key) for param, src_key in self.kwargs_from_state.items()}
        result = self.func(**kwargs) if kwargs else self.func()
        return {self.output_key: result}
