# src/composite_agents/test_graph/graph.py
#
# 🚀 Kick-start tutorial: how to build a small LangGraph composite
# ---------------------------------------------------------------
# What this graph does:
#   1) Ask an LLM to produce exactly 6 lowercase letters (e.g., "aabbcc").
#   2) Route by pattern:
#        - TRIPLE:   there exists a run of >= 3 identical letters (e.g., "aaab..")
#        - DOUBLE:   there exists a run of == 2 identical letters (e.g., "..bb..")
#        - NONE:     no consecutive identical letters
#   3) Branch logic:
#        - TRIPLE  → global filler → local filler → SCHEMA → END
#        - DOUBLE  → tool annotate → UPPERCASE(A) → SCHEMA → END
#        - NONE    → local sentence → refiner → min length(8) → UPPERCASE(A) → SCHEMA → END
#
# Why this file is useful as a template:
#   - Shows a tidy way to define a graph “state”, and to keep each node tiny.
#   - Wraps node callables with RunnableLambda so LangGraph type expectations are happy.
#   - Demonstrates mixing universal prompts (registry) + composite-local prompts.
#   - Demonstrates using a tool by NAME via a registry (no hard dependency on function symbols).
#   - Ends with a SchemaEnforcer so every composite returns the same contract: {"text": "..."}.
#
# How to extend:
#   - Add a new node: write a small `(state) -> delta` function and wire it with `g.add_node("name", rl(self._n_name))`.
#   - Add a new route: update `_route_from_letters` (or write a separate router node), then add conditional edges.
#   - Swap the tool: register a different callable under the same name at startup (see note near TOOL_REGISTRY).
#   - Make it async later: add `ainvoke` with the same steps and await LLM-backed agents (they already support async).

from __future__ import annotations
from typing import Dict, Any, Mapping, Literal, TypedDict, Callable, cast
import re

from langgraph.graph import StateGraph, END
from langchain_core.runnables import RunnableLambda  # wraps plain functions as graph nodes

# Universal (reusable) agents
from ...agents.llm_runner_agent import LLMRunnerAgent
from ...agents.refiner_agent import RefinerAgent
from ...agents.template_filler_agent import TemplateFillerAgent
from ...agents.python_tool_agent import PythonToolAgent
from ...agents.schema_enforcer_agent import SchemaEnforcerAgent

# Global prompt registry (e.g., "base")
from ...prompts import get_prompt

# Composite-local prompt (only used by this composite)
from .prompts.local_filler_prompt import LOCAL_FILLER_PROMPT

# Central tool registry. At app startup do:
#   registry.register("string.mark_double", lambda s: f"double::{s}")
from ...tools.registry import registry as TOOL_REGISTRY


# ─────────────────────────────────────────────────────────────────────────────
# 1) Graph state
#    Keep state minimal and readable. We use TypedDict with optional keys
#    so each node can add only the fields it produces.
# ─────────────────────────────────────────────────────────────────────────────

class GraphState(TypedDict, total=False):
    # Input
    user_input: str

    # After runner
    draft: str       # raw model output (may include newline)
    letters: str     # sanitized 6 letters, lowercase [a-z]

    # Routing decision
    route: Literal["TRIPLE", "DOUBLE", "NONE"]

    # Mid-way artifacts / final
    ann: str         # tool annotation (DOUBLE branch)
    text: str        # canonical “final candidate” we normalize at the end

# Narrow view: used only right after router to safely access route
class HasRoute(TypedDict):
    route: Literal["TRIPLE", "DOUBLE", "NONE"]


# Small helper to wrap node functions as Runnables for LangGraph
def rl(func: Callable[[GraphState], Dict[str, Any]]) -> RunnableLambda:
    return RunnableLambda(func)


class TestGraphComposite:
    """
    A friendly, annotated composite your teammates can copy:
      user_input → runner → router
        TRIPLE → global filler → local filler → schema → END
        DOUBLE → tool annotate → UPPERCASE(A) → schema → END
        NONE   → sentence(local) → refiner → minLen8 → UPPERCASE(A) → schema → END

    Public contract:
      .invoke({"user_input": ...}) -> {"text": "..."}
    """

    # ── Setup: create agent instances (DI-friendly; YAML agent overrides apply) ──
    def __init__(self, *, runner_llm=None, refiner_llm=None):
        # Reuse LLMRunner twice:
        #  - with a GLOBAL prompt from registry ("base")
        self.runner_global = LLMRunnerAgent(llm=runner_llm, prompt=get_prompt("base_text_only"))
        #  - with a COMPOSITE-LOCAL prompt
        self.runner_local_filler = LLMRunnerAgent(llm=runner_llm, prompt=LOCAL_FILLER_PROMPT)

        # Keep-intent refiner
        self.refiner = RefinerAgent(llm=refiner_llm)

        # Tool by NAME through registry (swappable at startup)
        self.double_annotator = PythonToolAgent(
            tool_name="string.mark_double",
            registry=TOOL_REGISTRY,
            output_key="ann",
            kwargs_from_state={"s": "letters"},  # pass state["letters"] to tool arg "s"
        )

        # Normalize final shape
        self.schema = SchemaEnforcerAgent(mode="text", prefer_key="text")

        self._graph = self._build_graph()

    # ── Pure helpers: small, testable Python utilities ──

    @staticmethod
    def _extract_letters(text: str) -> str:
        """Keep only [a-z], lowercased; ensure exactly 6 chars (pad conservatively if short)."""
        letters = "".join(re.findall(r"[a-z]", text.lower()))
        if len(letters) >= 6:
            return letters[:6]
        while len(letters) < 6 and letters:
            letters += letters[-1]
        return letters or "abcdef"  # final fallback for robustness

    @staticmethod
    def _route_from_letters(letters: str) -> str:
        """Return TRIPLE / DOUBLE / NONE based on consecutive runs."""
        if not letters:
            return "NONE"
        runs, streak = [], 1
        for i in range(1, len(letters)):
            if letters[i] == letters[i - 1]:
                streak += 1
            else:
                runs.append(streak)
                streak = 1
        runs.append(streak)
        if any(r >= 3 for r in runs):
            return "TRIPLE"
        if any(r == 2 for r in runs):
            return "DOUBLE"
        return "NONE"

    @staticmethod
    def _uppercase_A(state: Mapping[str, Any]) -> Dict[str, Any]:
        """Non-LLM post step “A”: pick ann → text → draft, then uppercase."""
        candidate = str(state.get("ann") or state.get("text") or state.get("draft", ""))
        return {"text": candidate.upper()}

    @staticmethod
    def _length_min8(state: Mapping[str, Any]) -> Dict[str, Any]:
        """Ensure text length ≥ 8; if short, append a tiny suffix for demo."""
        t = str(state.get("text", ""))
        return {"text": t if len(t) >= 8 else f"{t} ok."}

    # ── Nodes: each is (state) -> small delta dict ──

    def _n_runner(self, state: GraphState) -> Dict[str, Any]:
        """Ask the model for 6 random lowercase letters (continuous, no spaces/punct)."""
        ui = (
            "Generate exactly 6 random lowercase letters as a continuous string. "
            "No spaces, no punctuation, only [a-z]. Return letters only."
        )
        out = self.runner_global.invoke({"user_input": ui})
        draft = str(out.get("draft", ""))
        letters = self._extract_letters(draft)
        return {"draft": draft, "letters": letters}

    def _n_router(self, state: GraphState) -> Dict[str, Any]:
        """Decide which branch to take based on the letters pattern."""
        return {"route": self._route_from_letters(state.get("letters", ""))}

    # TRIPLE branch: global filler → local filler
    def _n_filler_global(self, state: GraphState) -> Dict[str, Any]:
        ui = f"Letters: {state.get('letters','')}\nCreate a 1-line short phrase that mentions them."
        out = self.runner_global.invoke({"user_input": ui})
        return {"text": str(out.get("draft", "")).strip()}

    def _n_filler_local(self, state: GraphState) -> Dict[str, Any]:
        out = self.runner_local_filler.invoke({"user_input": "", "letters": state.get("letters", "")})
        return {"text": str(out.get("draft", "")).strip()}

    # DOUBLE branch: tool annotate → uppercase A
    def _n_tool_annotate(self, state: GraphState) -> Dict[str, Any]:
        return self.double_annotator.invoke(state)

    def _n_uppercase_after_tool(self, state: GraphState) -> Dict[str, Any]:
        return self._uppercase_A(state)

    # NONE branch: local sentence → refiner → minLen8 → uppercase A
    def _n_sentence_local(self, state: GraphState) -> Dict[str, Any]:
        letters = state.get("letters", "")
        ui = f"Use letters '{letters}' in a simple, friendly short sentence."
        out = self.runner_global.invoke({"user_input": ui})
        return {"text": str(out.get("draft", "")).strip()}

    def _n_refine_sentence(self, state: GraphState) -> Dict[str, Any]:
        # Refiner expects 'draft'; we pass the sentence via a tiny adapter
        return self.refiner.invoke({"draft": state.get("text", "")})

    def _n_rule_len8(self, state: GraphState) -> Dict[str, Any]:
        return self._length_min8(state)

    def _n_uppercase_final(self, state: GraphState) -> Dict[str, Any]:
        return self._uppercase_A(state)

    # Shared: normalize to {"text": "..."}
    def _n_schema(self, state: GraphState) -> Dict[str, Any]:
        return self.schema.invoke(state)

    # ── Graph wiring: use RunnableLambda to satisfy LangGraph’s node type ──
    def _build_graph(self):
        g = StateGraph(GraphState)

        g.add_node("runner", rl(self._n_runner))
        g.add_node("router", rl(self._n_router))

        # TRIPLE
        g.add_node("filler_global", rl(self._n_filler_global))
        g.add_node("filler_local", rl(self._n_filler_local))

        # DOUBLE
        g.add_node("tool_annotate", rl(self._n_tool_annotate))
        g.add_node("uppercase_after_tool", rl(self._n_uppercase_after_tool))

        # NONE
        g.add_node("sentence_local", rl(self._n_sentence_local))
        g.add_node("refine_sentence", rl(self._n_refine_sentence))
        g.add_node("rule_len8", rl(self._n_rule_len8))
        g.add_node("uppercase_final", rl(self._n_uppercase_final))

        # Shared
        g.add_node("schema", rl(self._n_schema))

        g.set_entry_point("runner")
        g.add_edge("runner", "router")

        # Conditional branch; cast narrows away the “route may be missing” warning.
        def decide(state: GraphState) -> str:
            return cast(HasRoute, state)["route"]

        g.add_conditional_edges(
            "router",
            decide,
            {
                "TRIPLE": "filler_global",
                "DOUBLE": "tool_annotate",
                "NONE":   "sentence_local",
            },
        )

        # TRIPLE path
        g.add_edge("filler_global", "filler_local")
        g.add_edge("filler_local", "schema")

        # DOUBLE path
        g.add_edge("tool_annotate", "uppercase_after_tool")
        g.add_edge("uppercase_after_tool", "schema")

        # NONE path
        g.add_edge("sentence_local", "refine_sentence")
        g.add_edge("refine_sentence", "rule_len8")
        g.add_edge("rule_len8", "uppercase_final")
        g.add_edge("uppercase_final", "schema")

        g.add_edge("schema", END)
        return g.compile()

    # Public API: match other composites
    def invoke(self, state_in: Mapping[str, Any]) -> Dict[str, Any]:
        init: GraphState = {"user_input": str(state_in.get("user_input", ""))}
        out = self._graph.invoke(init)
        return {"text": str(out.get("text", ""))}
