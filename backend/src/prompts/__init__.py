from __future__ import annotations
from typing import Dict, Any
import importlib
import pkgutil
import re

from langchain_core.prompts import BasePromptTemplate

# Public registry (filled by discovery)
PROMPTS: Dict[str, BasePromptTemplate] = {}

_NAME_CLEAN = re.compile(r"_prompt$", re.IGNORECASE)

def _norm_from_attr(attr_name: str) -> str:
    """
    Convert VAR names like 'LLM_ROUTER_PROMPT' or 'BASE_TEXT_ONLY_PROMPT'
    to registry keys 'llm_router' and 'base_text_only'.
    """
    name = attr_name.lower()
    name = _NAME_CLEAN.sub("", name)           # strip trailing _prompt
    if name.endswith("_"):
        name = name[:-1]
    return name

def _register(name: str, prompt: BasePromptTemplate) -> None:
    if not isinstance(prompt, BasePromptTemplate):
        raise TypeError(f"Prompt '{name}' must be a BasePromptTemplate")
    PROMPTS[name] = prompt

def _register_from_module(mod) -> None:
    """
    Module registration rules:
    1) If module defines __all_prompts__ (dict[name, prompt]), use it exactly.
    2) Else, auto-pick any BasePromptTemplate attrs; key = normalized attr name.
    """
    custom = getattr(mod, "__all_prompts__", None)
    if isinstance(custom, dict):
        for k, v in custom.items():
            if isinstance(v, BasePromptTemplate):
                _register(k, v)
        return

    for attr, obj in vars(mod).items():
        if isinstance(obj, BasePromptTemplate):
            key = _norm_from_attr(attr)
            _register(key, obj)

def _discover() -> None:
    """
    Auto-import all submodules in this package whose name ends with '_prompt'.
    Register any BasePromptTemplate they expose.
    """
    pkg = importlib.import_module(__name__)
    for m in pkgutil.iter_modules(pkg.__path__):
        if m.ispkg:
            continue
        if not m.name.endswith("_prompt"):
            continue
        try:
            mod = importlib.import_module(f"{__name__}.{m.name}")
        except Exception as e:  # pragma: no cover
            # Keep registry resilient: skip broken prompt modules
            # (They can be fixed without blocking the whole system)
            continue
        _register_from_module(mod)

def reload_prompts() -> Dict[str, str]:
    """Dev helper: clear & re-discover prompts; return summary."""
    PROMPTS.clear()
    _discover()
    return list_prompts()

def get_prompt(name: str) -> BasePromptTemplate:
    try:
        return PROMPTS[name]
    except KeyError:
        raise KeyError(f"Unknown prompt: {name}. Known: {sorted(PROMPTS.keys())}")

def list_prompts() -> Dict[str, str]:
    return {k: type(v).__name__ for k, v in PROMPTS.items()}

# ---- initial discovery at import time ----
_discover()

__all__ = ["PROMPTS", "get_prompt", "list_prompts", "reload_prompts"]
