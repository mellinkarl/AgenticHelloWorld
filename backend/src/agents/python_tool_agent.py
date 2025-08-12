from __future__ import annotations
from typing import Mapping, Dict, Any, Optional

from ..config import get_logger
from ..core.instrumentation import log_invoke_start, log_invoke_end
from ..tools.registry import registry as default_registry, ToolRegistry

log = get_logger(__name__)

class PythonToolAgent:
    """
    Wraps a registered Python tool so it can be used as an Agent.

    Behavior:
        - Looks up a callable in a ToolRegistry by `tool_name`.
        - Builds the tool's arguments from `state` using `kwargs_from_state`.
        - Calls the tool (sync or async).
        - Stores the tool's result under `output_key` in the returned state.

    Args:
        tool_name:
            Name of the tool registered in the ToolRegistry.
        output_key:
            The key under which the tool's result will be stored in the output state.
        kwargs_from_state:
            Mapping of tool parameter names → state keys.
            Example:
                {"param1": "input_a", "param2": "input_b"}
            will call tool(param1=state["input_a"], param2=state["input_b"])
        registry:
            Optional custom ToolRegistry; defaults to the global registry.
    """

    def __init__(
        self,
        tool_name: str,
        *,
        output_key: str,
        kwargs_from_state: Optional[Dict[str, str]] = None,
        registry: Optional[ToolRegistry] = None,
    ):
        self.tool_name = tool_name
        self.output_key = output_key
        self.kwargs_from_state = kwargs_from_state or {}
        self.registry = registry or default_registry

    def _build_kwargs(self, state: Mapping[str, Any]) -> Dict[str, Any]:
        """
        Extracts and maps values from the state to match the tool's parameters.

        Args:
            state: Current state mapping.

        Returns:
            dict: Arguments to pass to the tool.
        """
        return {
            param: state.get(src_key)
            for param, src_key in self.kwargs_from_state.items()
        }

    def invoke(self, state: Mapping[str, Any]) -> Dict[str, Any]:
        """
        Synchronously invokes the registered tool.

        Args:
            state: Current state mapping.

        Returns:
            dict: {output_key: tool_result}
        """
        # Log the start of invocation
        t0 = log_invoke_start(log, "PythonToolAgent", state)

        # Prepare tool arguments from state
        kwargs = self._build_kwargs(state)

        # Call the tool (sync)
        result = self.registry.call(self.tool_name, **kwargs)

        # Build output mapping
        out = {self.output_key: result}

        # Log the end of invocation
        log_invoke_end(log, "PythonToolAgent", t0, out)
        return out

    async def ainvoke(self, state: Mapping[str, Any]) -> Dict[str, Any]:
        """
        Asynchronously invokes the registered tool.

        Args:
            state: Current state mapping.

        Returns:
            dict: {output_key: tool_result}
        """
        t0 = log_invoke_start(log, "PythonToolAgent", state)

        # Prepare tool arguments from state
        kwargs = self._build_kwargs(state)

        # Call the tool (async-aware)
        result = await self.registry.acall(self.tool_name, **kwargs)

        # Build output mapping
        out = {self.output_key: result}

        log_invoke_end(log, "PythonToolAgent", t0, out)
        return out
