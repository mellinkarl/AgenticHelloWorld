# #!/usr/bin/env python3
# # -*- coding: utf-8 -*-
# """
# Run real Vertex LLM on the paper context and capture input/middle/final outputs.
# Usable both as:  python src/runner/capture_context.py
#              and: python -m src.runner.capture_context

# Outputs (default): src/tests/context_run.auto.json
# - snapshots[] keeps step-by-step state (draft/route/today/tool_text/text/…)
# - final.text is the final output

# cmd: 
# - python src/runner/capture_context.py

# - python -m src.runner.capture_context

# - python src/runner/capture_context.py --paper src/tests/test_paper.py --out src/tests/context_run.auto.json
# """

# from __future__ import annotations
# import argparse, json, os, sys
# from pathlib import Path
# from typing import Any, Dict, List
# import importlib.util

# # ---- Make repo root importable when run as a script ----
# THIS_FILE = Path(__file__).resolve()
# SRC_DIR = THIS_FILE.parents[1]            # .../src
# REPO_ROOT = SRC_DIR.parent                # repo root
# if str(REPO_ROOT) not in sys.path:
#     sys.path.insert(0, str(REPO_ROOT))    # so `import src.xxx` works

# # ---- Project imports (absolute) ----
# from backend.src.config.config import Config
# from src.llm.vertex import get_vertex_chat_model

# # universal atomic agents
# from src.agents.llm_runner_agent import LLMRunnerAgent
# from src.agents.rule_router_agent import RuleRouterAgent
# from src.agents.llm_router_agent import LLMRouterAgent
# from src.agents.python_tool_agent import PythonToolAgent
# from src.agents.template_filler_agent import TemplateFillerAgent
# from src.agents.refiner_agent import RefinerAgent
# from src.agents.diff_enforcer_agent import DiffEnforcerAgent
# from src.agents.length_keyword_guard_agent import LengthKeywordGuardAgent
# from src.agents.schema_enforcer_agent import SchemaEnforcerAgent


# # ---------- helpers ----------
# def load_text_from_module(py_path: Path, var_name: str = "text") -> str:
#     if not py_path.exists():
#         raise FileNotFoundError(f"Cannot find: {py_path}")
#     spec = importlib.util.spec_from_file_location("paper_module", str(py_path))
#     if spec is None or spec.loader is None:
#         raise RuntimeError(f"Failed to load spec for {py_path}")
#     module = importlib.util.module_from_spec(spec)
#     spec.loader.exec_module(module)  # type: ignore[attr-defined]
#     if not hasattr(module, var_name):
#         raise AttributeError(f"{py_path} does not define `{var_name}`")
#     val = getattr(module, var_name)
#     if not isinstance(val, str):
#         raise TypeError(f"{var_name} must be a str, got {type(val)}")
#     return val


# KEYS_TO_TRACE = ["user_input", "draft", "route", "today", "tool_text", "text", "ok", "violations"]

# def _snapshot(label: str, state: Dict[str, Any]) -> Dict[str, Any]:
#     snap = {"step": label}
#     for k in KEYS_TO_TRACE:
#         if k in state:
#             snap[k] = state[k]
#     return snap

# def _llm_meta(cfg: Config, agent_key: str) -> dict:
#     kw = cfg.llm_kwargs(agent=agent_key)
#     return {
#         "agent": agent_key,
#         "model": kw.get("model"),
#         "temperature": kw.get("temperature"),
#         "max_output_tokens": kw.get("max_output_tokens"),
#         "response_mime_type": kw.get("response_mime_type"),
#         "project": cfg.project,
#         "location": cfg.location,
#     }


# # ---------- main ----------
# def main(argv=None) -> int:
#     parser = argparse.ArgumentParser(
#         description="Capture real LLM run on paper context and record all middle outputs."
#     )
#     parser.add_argument(
#         "--paper",
#         default=str(SRC_DIR / "tests" / "test_paper.py"),
#         help="Path to the Python file that defines `text = '''...'''`",
#     )
#     parser.add_argument(
#         "--out",
#         default=str(SRC_DIR / "tests" / "context_run.auto.json"),
#         help="Output JSON path",
#     )
#     args = parser.parse_args(argv)

#     paper_path = Path(args.paper)
#     paper_text = load_text_from_module(paper_path, "text").strip()

#     # 1) Init real Vertex environment
#     cfg = Config.load()
#     cfg.apply_google_env()
#     cfg.init_vertex()

#     # Build per-agent real LLMs (configurable via src/config/default.yaml)
#     runner_llm  = get_vertex_chat_model(cfg, agent="runner")
#     decider_llm = get_vertex_chat_model(cfg, agent="decider")
#     refiner_llm = get_vertex_chat_model(cfg, agent="refiner")

#     # 2) Instantiate universal agents
#     runner  = LLMRunnerAgent(llm=runner_llm)
#     rule_rt = RuleRouterAgent(
#         min_len=1, max_len=10000, must_include=[], forbid=[], require_json=False
#     )
#     llm_rt   = LLMRouterAgent(llm=decider_llm)
#     tool     = PythonToolAgent(func=lambda: __import__("datetime").date.today().isoformat(), output_key="today")
#     templ    = TemplateFillerAgent("{today} OK", output_key="tool_text")
#     refiner  = RefinerAgent(llm=refiner_llm, requirements="Improve clarity/format without changing meaning.")
#     differ   = DiffEnforcerAgent(text_key="text", draft_key="draft", use_suffix_key="today", fallback_suffix=" (modified)")
#     guard    = LengthKeywordGuardAgent(source_key="text", must_include=[], max_len=10000)
#     schema   = SchemaEnforcerAgent(mode="text", prefer_key="text")

#     # 3) Drive linear pipeline and capture snapshots
#     state: Dict[str, Any] = {"user_input": paper_text}
#     snaps: List[Dict[str, Any]] = []

#     state.update(runner.invoke(state));             snaps.append(_snapshot("LLMRunner", state))
#     state.update(rule_rt.invoke(state));            snaps.append(_snapshot("RuleRouter", state))
#     state.update(llm_rt.invoke(state));             snaps.append(_snapshot("LLMRouter", state))
#     state.update(tool.invoke(state));               snaps.append(_snapshot("PythonTool(date)", state))
#     state.update(templ.invoke(state));              snaps.append(_snapshot("TemplateFiller", state))
#     state.update(refiner.invoke(state));            snaps.append(_snapshot("Refiner", state))

#     # route policy
#     route = str(state.get("route", "REFINE"))
#     if route == "REFINE_DATE" and state.get("tool_text"):
#         state["text"] = str(state["tool_text"])
#     elif route == "PASS" and state.get("draft"):
#         state["text"] = str(state["draft"])
#     else:
#         state["text"] = str(state.get("text", ""))

#     snaps.append(_snapshot("Chooser", state))
#     state.update(differ.invoke(state));             snaps.append(_snapshot("DiffEnforcer", state))
#     state.update(guard.invoke(state));              snaps.append(_snapshot("Guard", state))
#     state.update(schema.invoke(state));             snaps.append(_snapshot("SchemaEnforcer", state))

#     # 4) Assemble record
#     record = {
#         "llm": {
#             "runner":  _llm_meta(cfg, "runner"),
#             "decider": _llm_meta(cfg, "decider"),
#             "refiner": _llm_meta(cfg, "refiner"),
#         },
#         "input": {
#             "file": str(paper_path),
#             "chars": len(paper_text),
#         },
#         "snapshots": snaps,
#         "final": {"text": str(state.get("text", ""))},
#     }

#     # 5) Persist
#     out_path = Path(args.out)
#     out_path.parent.mkdir(parents=True, exist_ok=True)
#     out_path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")

#     print(json.dumps(record["final"], ensure_ascii=False, indent=2))
#     print(f"[WROTE] {out_path.resolve()}", file=sys.stderr)
#     return 0


# if __name__ == "__main__":
#     raise SystemExit(main())
