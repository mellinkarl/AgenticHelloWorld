# src/runner/run_graph.py
'''
# Option A:
python -m src.runner.run_graph --input "Say exactly: OK."
# => {"text":"OK."}

# Option B:
python -m src.runner.run_graph --input "Say: hi" --force_refine
# => {"text":"OK."}
'''

from __future__ import annotations
import argparse, json, sys
from typing import cast

from ..config import Config
from ..llm.vertex import get_vertex_chat_model
from ..agents.runner_agent import RunnerAgent
from ..agents.router_agent import RouterAgent
from ..agents.refiner_agent import RefinerAgent
from ..graph.minimal_graph import build_minimal_graph, GraphState
from ..schemas.io import SimpleOutput

def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Run minimal Runner→Router→(Refiner) graph.")
    parser.add_argument("--input", required=True, help="User input text.")
    parser.add_argument("--force_refine", action="store_true", help="Force routing to Refiner.")
    args = parser.parse_args(argv)

    # 1) Config & Vertex init
    cfg = Config.load()
    cfg.apply_google_env()
    cfg.init_vertex()

    # 2) LLMs (per-agent overrides supported via default.yaml)
    runner_llm  = get_vertex_chat_model(cfg, agent="runner")
    refiner_llm = get_vertex_chat_model(cfg, agent="refiner")

    # 3) Agents
    runner  = RunnerAgent(runner_llm)
    router  = RouterAgent(require_exact="OK.")
    refiner = RefinerAgent(refiner_llm, requirements="The final output must be exactly 'OK.'")

    # 4) Graph
    graph = build_minimal_graph(runner, router, refiner)

    # 5) Execute (type-hint the state so Pylance is satisfied)
    init_state: GraphState = {
        "user_input": args.input,
        "force_refine": args.force_refine,
    }
    final_state = cast(GraphState, graph.invoke(init_state))

    # 6) Normalize & print
    out = SimpleOutput(text=final_state.get("text", ""))
    print(json.dumps(out.model_dump(), ensure_ascii=False, indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
