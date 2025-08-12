# src/app/routes/agents.py
from __future__ import annotations

import time
import inspect
from typing import Any, Dict, List, Optional, Callable, cast

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ...config import Config, get_logger
from ...llm.vertex import get_vertex_chat_model

# Universal agents
from ...agents.llm_runner_agent import LLMRunnerAgent
from ...agents.rule_router_agent import RuleRouterAgent
from ...agents.llm_router_agent import LLMRouterAgent
from ...agents.refiner_agent import RefinerAgent
from ...agents.schema_enforcer_agent import SchemaEnforcerAgent
from ...agents.length_keyword_guard_agent import LengthKeywordGuardAgent
from ...agents.diff_enforcer_agent import DiffEnforcerAgent
from ...agents.python_tool_agent import PythonToolAgent
from ...agents.template_filler_agent import TemplateFillerAgent

# Optional: prompt registry for runtime selection
from ...prompts import get_prompt

log = get_logger(__name__)
router = APIRouter(prefix="/agents", tags=["agents"])


# ---------- Schemas ----------
class InvokeRequest(BaseModel):
    state: Dict[str, Any] = Field(default_factory=dict)
    args: Dict[str, Any] = Field(default_factory=dict)
    async_mode: bool = False

class InvokeResponse(BaseModel):
    agent: str
    ms: int
    state_in: Dict[str, Any]
    state_out: Dict[str, Any]

class PythonToolArgs(BaseModel):
    tool_name: str
    output_key: str
    kwargs_from_state: Optional[Dict[str, str]] = None

class PythonToolInvokeRequest(BaseModel):
    state: Dict[str, Any] = Field(default_factory=dict)
    args: PythonToolArgs
    async_mode: bool = False

class TemplateFillerArgs(BaseModel):
    template: str
    output_key: str = "text"

class TemplateFillerInvokeRequest(BaseModel):
    state: Dict[str, Any] = Field(default_factory=dict)
    args: TemplateFillerArgs
    async_mode: bool = False


# ---------- Helpers ----------
async def _invoke_agent_maybe_async(agent: Any, state: Dict[str, Any], async_mode: bool) -> Dict[str, Any]:
    """
    Call agent. Prefer ainvoke when async_mode=True and available.
    Always return Dict[str, Any] or raise 500 if the agent returns a non-dict.
    """
    if async_mode:
        maybe = getattr(agent, "ainvoke", None)
        if callable(maybe):
            result = maybe(state)
            if inspect.isawaitable(result):
                result = await result
            if not isinstance(result, dict):
                raise HTTPException(500, f"Agent {type(agent).__name__} returned non-dict from ainvoke: {type(result).__name__}")
            return cast(Dict[str, Any], result)

    # Fallback to sync invoke
    result = agent.invoke(state)
    if not isinstance(result, dict):
        raise HTTPException(500, f"Agent {type(agent).__name__} returned non-dict from invoke: {type(result).__name__}")
    return cast(Dict[str, Any], result)


def _normalize(name: str) -> str:
    return name.replace("-", "").replace("_", "").lower()


# ---------- Specialized endpoints FIRST ----------
@router.post("/python-tool/invoke", response_model=InvokeResponse)
async def invoke_python_tool(req: PythonToolInvokeRequest) -> InvokeResponse:
    cfg = Config.load()
    t0 = time.perf_counter()

    agent = PythonToolAgent(
        tool_name=req.args.tool_name,
        output_key=req.args.output_key,
        kwargs_from_state=req.args.kwargs_from_state or {},
    )
    out: Dict[str, Any] = await _invoke_agent_maybe_async(agent, req.state, req.async_mode)

    ms = int((time.perf_counter() - t0) * 1000)
    return InvokeResponse(agent="PythonToolAgent", ms=ms, state_in=req.state, state_out=out)


@router.post("/template-filler/invoke", response_model=InvokeResponse)
async def invoke_template_filler(req: TemplateFillerInvokeRequest) -> InvokeResponse:
    t0 = time.perf_counter()

    agent = TemplateFillerAgent(
        template=req.args.template,
        output_key=req.args.output_key,
    )
    out: Dict[str, Any] = await _invoke_agent_maybe_async(agent, req.state, req.async_mode)

    ms = int((time.perf_counter() - t0) * 1000)
    return InvokeResponse(agent="TemplateFillerAgent", ms=ms, state_in=req.state, state_out=out)


# ---------- Agent factory registry (for generic endpoint) ----------
def _build_llm_runner(cfg: Config, args: Dict[str, Any]):
    llm = get_vertex_chat_model(cfg, agent="runner")
    prompt = get_prompt(args["prompt_name"]) if "prompt_name" in args else None
    return LLMRunnerAgent(llm, prompt=prompt)

def _build_rule_router(cfg: Config, args: Dict[str, Any]):
    return RuleRouterAgent(**args)

def _build_llm_router(cfg: Config, args: Dict[str, Any]):
    llm = get_vertex_chat_model(cfg, agent="decider")
    return LLMRouterAgent(llm)

def _build_refiner(cfg: Config, args: Dict[str, Any]):
    llm = get_vertex_chat_model(cfg, agent="refiner")
    requirements = args.get("requirements", "Keep intent; improve clarity only.")
    return RefinerAgent(llm, requirements=requirements)

def _build_schema_enforcer(cfg: Config, args: Dict[str, Any]):
    return SchemaEnforcerAgent(**args)

def _build_length_keyword_guard(cfg: Config, args: Dict[str, Any]):
    return LengthKeywordGuardAgent(**args)

def _build_diff_enforcer(cfg: Config, args: Dict[str, Any]):
    return DiffEnforcerAgent(**args)

AGENT_BUILDERS: Dict[str, Callable[[Config, Dict[str, Any]], Any]] = {
    "llmrunneragent": _build_llm_runner,
    "rulerouteragent": _build_rule_router,
    "llmrouteragent": _build_llm_router,
    "refineragent": _build_refiner,
    "schemaenforceragent": _build_schema_enforcer,
    "lengthkeywordguardagent": _build_length_keyword_guard,
    "diffenforceragent": _build_diff_enforcer,
}


@router.get("", response_model=List[str])
def list_agents() -> List[str]:
    return sorted(list(AGENT_BUILDERS.keys()) + ["python-tool*", "template-filler*"])


def _build_agent_or_404(agent_name: str, cfg: Config, args: Dict[str, Any]) -> Any:
    key = _normalize(agent_name)
    if key not in AGENT_BUILDERS:
        raise HTTPException(404, f"Unknown agent: {agent_name}")
    try:
        return AGENT_BUILDERS[key](cfg, args)
    except TypeError as e:
        raise HTTPException(400, f"Invalid args for {agent_name}: {e}") from e
    except Exception as e:
        raise HTTPException(500, f"Failed to build agent {agent_name}: {e}") from e


# ---------- Generic invoke (after specialized endpoints) ----------
@router.post("/{agent_name}/invoke", response_model=InvokeResponse)
async def invoke_agent(agent_name: str, req: InvokeRequest) -> InvokeResponse:
    cfg = Config.load()
    t0 = time.perf_counter()

    agent = _build_agent_or_404(agent_name, cfg, req.args)
    out: Dict[str, Any] = await _invoke_agent_maybe_async(agent, req.state, req.async_mode)

    ms = int((time.perf_counter() - t0) * 1000)
    return InvokeResponse(agent=agent_name, ms=ms, state_in=req.state, state_out=out)
