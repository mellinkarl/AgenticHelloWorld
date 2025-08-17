# amie/agents/__init__.py
# Author: Harry
# 2025-08-16
"""Agent package for the AMIE system.

This package groups all individual agent definitions.  Each agent is
implemented in its own module and exposes a single callable that can be
registered with the LangGraph ``StateGraph``.  The callable signature
conforms to the LangGraph node protocol: it accepts the current
``GraphState`` and may return a partial update to that state or a
``Command`` instructing the graph which node to execute next.

Only minimal, skeleton implementations are provided here.  The actual
business logic should be filled in by developers following the
recommendations and patterns demonstrated in the official LangGraph and
LangChain templates.  For example, agent functions should call tools or
LLMs, update the graph state, and log progress.  Ensure all logic is
idempotent and respects the reducer semantics of each channel.
"""

from .ia import INGESTION
from .idca import INVENTION_D_C
from .naa import NOVELTY_A
from .aa import AGGREGATION

__all__ = [
    "INGESTION",
    "INVENTION_D_C",
    "NOVELTY_A",
    "AGGREGATION",
]
