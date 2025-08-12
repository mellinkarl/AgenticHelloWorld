from __future__ import annotations
from typing import Dict, Any, Mapping, Optional, Callable
import json
import sys

from ...agents.llm_runner_agent import LLMRunnerAgent
from ...agents.rule_router_agent import RuleRouterAgent
from ...agents.llm_router_agent import LLMRouterAgent
from ...agents.template_filler_agent import TemplateFillerAgent
from ...agents.python_tool_agent import PythonToolAgent
from ...agents.diff_enforcer_agent import DiffEnforcerAgent
from ...agents.length_keyword_guard_agent import LengthKeywordGuardAgent
from ...agents.schema_enforcer_agent import SchemaEnforcerAgent
from ...agents.refiner_agent import RefinerAgent

# we only use the tool registry by name (no direct function import)
from ...tools.registry import registry as TOOL_REGISTRY
from .conditioners.rules import RULES


def _tap(label: str, state: Mapping[str, Any]) -> None:
    """
    Minimal, stdout-based probe: print a small "snapshot" of state after each step.
    - This is intentionally simple (stderr printing) so the composite can be run
      in CLI/pytest without depending on logging config.
    - For production, replace this with your JSON logger (keeping the same keys).

    TIP: Keep snapshots tiny & stable (keys below). The more deterministic your
    snapshot is, the easier it is to build "golden" tests.
    """
    snap_keys = ["user_input", "draft", "route", "today", "tool_text", "text", "ok", "violations"]
    view = {k: state.get(k) for k in snap_keys if k in state}
    print(f"[{label}] {json.dumps(view, ensure_ascii=False)}", file=sys.stderr)


class TestLinearComposite:
    """
    A didactic, linear composite that demonstrates how to chain reusable universal agents.

    ┌───────────────────────────────────────────────────────────────────────┐
    │ Pipeline (single pass)                                                │
    │                                                                       │
    │  user_input → LLMRunner → RuleRouter → LLMRouter                      │
    │              → PythonTool(date.today) → TemplateFiller("{today} OK")  │
    │              → Refiner → Choose(draft|tool_text|text)                 │
    │              → DiffEnforcer → Guard → SchemaEnforcer → {"text": ...}  │
    └───────────────────────────────────────────────────────────────────────┘

    # Contract (very important to keep consistent across composites)
    - Input:  Mapping[str, Any] with at least {"user_input": str}
    - Output: Dict[str, Any] with exactly {"text": str} (final, normalized)

    # Why this structure?
    - Each agent is "one small step": read as little as needed; return a small
      delta dict. The composite becomes a declarative list of steps.
    - The composite itself does orchestration (branching/choosing), but does not
      “know” LLM details: model, temperature, parsing rules are encapsulated by agents.

    # How to write a similar composite
    1) List the reusable agents you need.
    2) Decide tool calls and where to store their outputs in state.
    3) Define a "chooser" policy (how to pick the final text).
    4) Add guardrails and a final schema enforcer (normalize output).
    5) Keep snapshot taps (or logs) after each step for testability.
    """

    # Explicit attribute type helps type-checkers and readers.
    choose: Callable[[Mapping[str, Any]], str]

    @staticmethod
    def _default_choose(state: Mapping[str, Any]) -> str:
        """
        Default final-choice policy. Tweak this to encode your composite's “business rule”.

        - If the LLMRouter decided we need a date-aware refinement ("REFINE_DATE"),
          and the template produced 'tool_text', prefer that (e.g., "2025-08-12 OK").
        - Else if the rule router said "PASS" and we have a draft, return the draft as-is.
        - Else fall back to the refiner's output 'text'.

        NOTE:
        - We deliberately strip only the 'draft' (LLM models often add trailing newline).
        - Missing keys are treated as empty strings to avoid KeyError.
        """
        route = str(state.get("route", "REFINE"))
        if route == "REFINE_DATE" and state.get("tool_text"):
            return str(state["tool_text"])
        if route == "PASS" and state.get("draft"):
            return str(state["draft"]).strip()
        return str(state.get("text", ""))

    def __init__(
        self,
        *,
        # LLM handles (if you use a DI container or a factory, inject them here).
        # Each LLM-backed agent can read per-agent overrides from YAML (runner/refiner/decider).
        runner_llm=None,
        decider_llm=None,
        refiner_llm=None,

        # Overridable, pre-built agents:
        # In real projects, this enables A/B testing and composition via dependency injection.
        llm_runner: Optional[LLMRunnerAgent] = None,
        rule_router: Optional[RuleRouterAgent] = None,
        llm_router: Optional[LLMRouterAgent] = None,
        refiner: Optional[RefinerAgent] = None,

        # Tools / template renderers:
        # Keep tool calls *named* (via registry) to allow runtime replacement and auditing.
        date_tool: Optional[PythonToolAgent] = None,
        template: Optional[TemplateFillerAgent] = None,

        # Post-processing & guardrails:
        diff_enforcer: Optional[DiffEnforcerAgent] = None,
        guard: Optional[LengthKeywordGuardAgent] = None,
        schema_enforcer: Optional[SchemaEnforcerAgent] = None,

        # Choosing policy for the final text:
        choose: Optional[Callable[[Mapping[str, Any]], str]] = None,
    ):
        # ---- LLM-backed universal agents ------------------------------------
        # LLMRunner: prompt → model → parse → {"draft": str}
        # - To select a different universal prompt at runtime (e.g., via FastAPI),
        #   create LLMRunnerAgent(llm, prompt=get_prompt("runner/personal"))
        self.llm_runner = llm_runner or LLMRunnerAgent(llm=runner_llm)

        # RuleRouter: deterministic gating (no tokens/cost)
        # You can change RULES["router"] to include len/keyword/JSON checks, etc.
        self.rule_router = rule_router or RuleRouterAgent(**RULES["router"])

        # LLMRouter: when rules are not enough, ask the model to decide a route label.
        # Typical labels: PASS | REFINE | REFINE_DATE | HUMAN_CHECK
        self.llm_router = llm_router or LLMRouterAgent(llm=decider_llm)

        # Refiner: “keep intent, improve clarity/format/completeness”
        self.refiner = refiner or RefinerAgent(
            llm=refiner_llm,
            requirements="Keep intent; improve clarity only.",
        )

        # ---- Tools & template ------------------------------------------------
        # We call tools by *name* through the registry. This allows:
        # - Centralized registration during app startup
        # - Swapping implementations without editing composites
        # - Narrow audit: "which code ran for tool 'date.today'?"
        # Make sure app startup has: registry.register("date.today", get_today_iso)
        self.date_tool = date_tool or PythonToolAgent(
            tool_name="date.today",
            registry=TOOL_REGISTRY,
            output_key="today",        # state["today"] will be set to YYYY-MM-DD
        )

        # TemplateFiller: render "{today} OK" using values from state.
        # - Non-strict: missing keys produce the original template (helps debugging).
        self.template = template or TemplateFillerAgent(
            template="{today} OK",
            output_key="tool_text",    # write rendered string here
        )

        # ---- Post-processing & guardrails -----------------------------------
        # DiffEnforcer: ensure the final text differs from the original draft.
        # If equal and 'tool_text' exists, we replace with tool_text; else append a suffix.
        self.diff_enforcer = diff_enforcer or DiffEnforcerAgent(
            text_key="text",
            draft_key="draft",
            use_suffix_key="tool_text",  # prefer replacing with this key's value
        )

        # LengthKeywordGuard: objective checks (min/max length, must_include, forbid, regex).
        # We read rules from a central RULES["guard"] (testable/configurable).
        self.guard = guard or LengthKeywordGuardAgent(
            **RULES["guard"],
            source_key="text",          # evaluate guard on the final text
        )

        # SchemaEnforcer: normalize to {"text": "..."} (or {"json": {...}} in JSON mode).
        # This is the canonical “output contract” for composites.
        self.schema_enforcer = schema_enforcer or SchemaEnforcerAgent(
            mode="text",
            prefer_key="text",          # if multiple candidates exist, prefer "text"
        )

        # Final chooser: policy for which field becomes the final "text".
        # Keep this replaceable to let other teams override business rules easily.
        self.choose = choose or self.__class__._default_choose

    def invoke(self, init: Mapping[str, Any]) -> Dict[str, Any]:
        """
        Run the pipeline once, merging each agent's delta back into `state`.

        IMPORTANT:
        - We keep state as a plain dict (JSON-serializable) and explicitly write the
          final contract {"text": "..."} at the end.
        - Avoid in-place mutations other than state.update(delta) for clarity & testing.
        """
        # 0) Seed required input keys. If upstream didn't pass user_input, default to "".
        state: Dict[str, Any] = {"user_input": str(init.get("user_input", ""))}

        # 1) Draft: prompt → LLM → parse
        state.update(self.llm_runner.invoke(state));      _tap("LLMRunner", state)

        # 2) Cheap rule-based routing
        state.update(self.rule_router.invoke(state));     _tap("RuleRouter", state)

        # 3) LLM-based routing (fallback/augmentation)
        state.update(self.llm_router.invoke(state));      _tap("LLMRouter", state)

        # 4) Tooling phase (always by registry name)
        #    Example: registry["date.today"]() → "YYYY-MM-DD"
        state.update(self.date_tool.invoke(state));       _tap("PythonTool(date.today)", state)

        # 5) Turn tool outputs into a candidate surface (non-LLM, deterministic)
        state.update(self.template.invoke(state));        _tap("TemplateFiller", state)

        # 6) Optional refinement (keep intent; improve clarity)
        state.update(self.refiner.invoke(state));         _tap("Refiner", state)

        # 7) Decide which candidate wins as “the” final text
        state["text"] = self.choose(state);               _tap("Chooser", state)

        # 8) Enforce difference from the original draft (avoid identity outputs)
        state.update(self.diff_enforcer.invoke(state));   _tap("DiffEnforcer", state)

        # 9) Objective guard checks (len/keywords/regex)
        state.update(self.guard.invoke(state));           _tap("Guard", state)

        # 10) Normalize to the canonical output contract
        state.update(self.schema_enforcer.invoke(state)); _tap("SchemaEnforcer", state)

        # Return exactly the contract the API expects
        return {"text": str(state.get("text", ""))}


# ─────────────────────────────────────────────────────────────────────────────
# HOW TO ADAPT THIS FILE FOR YOUR OWN COMPOSITE
#
# 1) Swap or add tools:
#    - Register a new callable at app startup:
#        registry.register("math.add", lambda a,b: a+b)
#    - Use it here:
#        self.calc = PythonToolAgent(tool_name="math.add",
#                                    registry=TOOL_REGISTRY,
#                                    output_key="sum",
#                                    kwargs_from_state={"a": "num_a", "b": "num_b"})
#    - Then render with TemplateFiller, or route on its result, etc.
#
# 2) Change LLM prompt/parameters:
#    - Universal prompt: pass prompt_name via HTTP args to LLMRunnerAgent,
#      or inject a prompt object directly in Python (LLMRunnerAgent(prompt=...)).
#    - Per-agent LLM settings come from YAML under `agents.runner/refiner/decider`.
#
# 3) Add branching:
#    - Keep each branch a plain sequence of agents.
#    - Store branch decisions (e.g., "route") in state; branch via Python if/else.
#
# 4) Make it async/streaming later:
#    - Most agents expose `ainvoke(...)`. Your composite can add an `ainvoke`
#      that awaits the same sequence. For token streaming, wire `astream_events`
#      in LLM-backed agents and surface via SSE/WebSocket at the API layer.
#
# 5) Testing:
#    - Replace LLMs with a FakeListChatModel, run invoke(), snapshot `_tap`
#      outputs or record intermediate states; compare to golden JSON.
# ─────────────────────────────────────────────────────────────────────────────
