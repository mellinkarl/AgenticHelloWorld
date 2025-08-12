from __future__ import annotations
import asyncio
import inspect
from typing import Any, Callable, Dict, Optional

class ToolRegistry:
    """
    A simple registry for tools (functions) that supports both
    synchronous and asynchronous callables.

    Main Features:
        - register(name, func):
            Store a callable (sync or async) under a string name.
        - call(name, **kwargs):
            Synchronous call to the registered function.
            Raises if the tool does not exist.
        - acall(name, **kwargs):
            Asynchronous call to the registered function.
            - If the function is async, awaits it directly.
            - If the function is sync, runs it in a background thread
              (via asyncio.to_thread) to avoid blocking the event loop.
    """

    def __init__(self) -> None:
        # Internal mapping: tool name → callable
        self._tools: Dict[str, Callable[..., Any]] = {}

    def register(self, name: str, func: Callable[..., Any]) -> None:
        """
        Register a callable tool under the given name.

        Args:
            name: Unique name of the tool.
            func: A callable (sync or async).

        Raises:
            TypeError: If `func` is not callable.
        """
        if not callable(func):
            raise TypeError("func must be callable")
        self._tools[name] = func

    def get(self, name: str) -> Callable[..., Any]:
        """
        Retrieve the registered callable for the given name.

        Args:
            name: Name of the tool to retrieve.

        Returns:
            Callable: The registered function.

        Raises:
            KeyError: If the tool name is not found.
        """
        if name not in self._tools:
            raise KeyError(f"Tool not found: {name}")
        return self._tools[name]

    def call(self, name: str, **kwargs) -> Any:
        """
        Call the registered tool synchronously.

        Args:
            name: Tool name.
            **kwargs: Arguments passed to the tool.

        Returns:
            Any: Result of the tool execution.
        """
        func = self.get(name)
        return func(**kwargs)

    async def acall(self, name: str, **kwargs) -> Any:
        """
        Call the registered tool asynchronously.

        Args:
            name: Tool name.
            **kwargs: Arguments passed to the tool.

        Returns:
            Any: Result of the tool execution.

        Notes:
            - Async functions are awaited directly.
            - Sync functions are executed in a thread to avoid blocking.
        """
        func = self.get(name)
        if inspect.iscoroutinefunction(func):
            return await func(**kwargs)
        # Run synchronous function in a thread to keep event loop responsive
        return await asyncio.to_thread(func, **kwargs)


# Global default registry instance
registry = ToolRegistry()
