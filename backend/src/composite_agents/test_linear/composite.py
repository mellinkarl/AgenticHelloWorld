from __future__ import annotations
from typing import Dict, Any, Mapping, Optional, Callable
import json, sys

from ...core.agent_protocol import Agent
from ...agents.llm_runner_agent import LLMRunnerAgent
from ...agents.rule_router_agent import RuleRouterAgent
from ...agents.llm_router_agent import LLMRouterAgent
from ...agents.template_filler_agent import TemplateFillerAgent
from ...agents.python_tool_agent import PythonToolAgent
from ...agents.diff_enforcer_agent import DiffEnforcerAgent
from ...agents.length_keyword_guard_agent import LengthKeywordGuardAgent
from ...agents.schema_enforcer_agent import SchemaEnforcerAgent
from ...agents.refiner_agent import RefinerAgent
from ...tools.date_tool import get_today_iso
from .conditioners.rules import RULES

def _tap(label: str, state: Mapping[str, Any]) -> None:
    snap_keys = ["user_input", "draft", "route", "today", "tool_text", "text", "ok", "violations"]
    view = {k: state.get(k) for k in snap_keys if k in state}
    print(f"[{label}] {json.dumps(view, ensure_ascii=False)}", file=sys.stderr)

class TestLinearComposite:
    """Linear demo composite that runs the universal agents once each and prints after every step."""

    # 显式声明实例属性类型，便于 Pylance 识别
    choose: Callable[[Mapping[str, Any]], str]

    @staticmethod
    def _default_choose(state: Mapping[str, Any]) -> str:
        """Default policy:
        - If route == REFINE_DATE and tool_text exists -> use tool_text
        - Else if route == PASS and draft exists      -> use draft
        - Else                                        -> use text (from refiner)
        """
        route = str(state.get("route", "REFINE"))
        if route == "REFINE_DATE" and state.get("tool_text"):
            return str(state["tool_text"])
        if route == "PASS" and state.get("draft"):
            return str(state["draft"])
        return str(state.get("text", ""))

    def __init__(
        self,
        *,
        # LLMs (injected by runner, using existing config.py)
        runner_llm=None,
        decider_llm=None,
        refiner_llm=None,
        # Overridable pre-built agents
        llm_runner: Optional[Agent] = None,
        rule_router: Optional[Agent] = None,
        llm_router: Optional[Agent] = None,
        refiner: Optional[Agent] = None,
        date_tool: Optional[Agent] = None,
        template: Optional[Agent] = None,
        diff_enforcer: Optional[Agent] = None,
        guard: Optional[Agent] = None,
        schema_enforcer: Optional[Agent] = None,
        choose: Optional[Callable[[Mapping[str, Any]], str]] = None,
    ):
        # --- build agents using injected LLMs ---
        self.llm_runner = llm_runner or LLMRunnerAgent(llm=runner_llm)
        self.rule_router = rule_router or RuleRouterAgent(**RULES["router"])
        self.llm_router = llm_router or LLMRouterAgent(llm=decider_llm)
        self.refiner = refiner or RefinerAgent(llm=refiner_llm, requirements="Keep intent; improve clarity only.")

        # tools / utils
        self.date_tool = date_tool or PythonToolAgent(get_today_iso, output_key="today")
        self.template = template or TemplateFillerAgent("{today} OK", output_key="tool_text")
        self.diff_enforcer = diff_enforcer or DiffEnforcerAgent(text_key="text", draft_key="draft", use_suffix_key="today")
        self.guard = guard or LengthKeywordGuardAgent(**RULES["guard"], source_key="text")
        self.schema_enforcer = schema_enforcer or SchemaEnforcerAgent(mode="text", prefer_key="text")

        # __class__ static method
        self.choose = choose or self.__class__._default_choose

    def invoke(self, init: Mapping[str, Any]) -> Dict[str, Any]:
        state: Dict[str, Any] = {"user_input": str(init.get("user_input", ""))}

        state.update(self.llm_runner.invoke(state));      _tap("LLMRunner", state)
        state.update(self.rule_router.invoke(state));     _tap("RuleRouter", state)
        state.update(self.llm_router.invoke(state));      _tap("LLMRouter", state)

        state.update(self.date_tool.invoke(state));       _tap("PythonTool(date)", state)
        state.update(self.template.invoke(state));        _tap("TemplateFiller", state)

        state.update(self.refiner.invoke(state));         _tap("Refiner", state)

        state["text"] = self.choose(state);               _tap("Chooser", state)
        state.update(self.diff_enforcer.invoke(state));   _tap("DiffEnforcer", state)
        state.update(self.guard.invoke(state));           _tap("Guard", state)
        state.update(self.schema_enforcer.invoke(state)); _tap("SchemaEnforcer", state)

        return {"text": str(state.get("text", ""))}
