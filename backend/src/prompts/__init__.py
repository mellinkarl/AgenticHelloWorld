from __future__ import annotations
from typing import Dict, Any

# Core prompts shipped with the repo
from .base_prompt import BASE_PROMPT
from .refiner_prompt import REFINER_PROMPT

# If present in your tree, keep this import; otherwise you can remove it.
try:
    from .llm_router_prompt import LLM_ROUTER_PROMPT  # noqa: F401
    _HAS_LLM_ROUTER = True
except Exception:  # pragma: no cover
    LLM_ROUTER_PROMPT = None  # type: ignore
    _HAS_LLM_ROUTER = False

# ---- Registry ---------------------------------------------------------------

PROMPTS: Dict[str, Any] = {
    "base": BASE_PROMPT,
    "refiner": REFINER_PROMPT,
}

if _HAS_LLM_ROUTER and LLM_ROUTER_PROMPT is not None:
    PROMPTS["llm_router"] = LLM_ROUTER_PROMPT

def register_prompt(name: str, prompt: Any) -> None:
    """
    Register a universal prompt under a string name.
    Example:
        from langchain_core.prompts import ChatPromptTemplate
        P = ChatPromptTemplate.from_messages([...])
        register_prompt("runner/personal", P)
    """
    if not name or not isinstance(name, str):
        raise ValueError("Prompt name must be a non-empty string.")
    PROMPTS[name] = prompt

def get_prompt(name: str) -> Any:
    """
    Lookup a registered universal prompt by name.
    Raises KeyError if not found.
    """
    if name not in PROMPTS:
        raise KeyError(f"Unknown prompt: {name}. Known: {sorted(PROMPTS.keys())}")
    return PROMPTS[name]

def list_prompts() -> Dict[str, str]:
    """Return a shallow view of available prompt names (for diagnostics)."""
    return {k: type(v).__name__ for k, v in PROMPTS.items()}

__all__ = [
    "BASE_PROMPT",
    "REFINER_PROMPT",
    "LLM_ROUTER_PROMPT",
    "PROMPTS",
    "get_prompt",
    "register_prompt",
    "list_prompts",
]
