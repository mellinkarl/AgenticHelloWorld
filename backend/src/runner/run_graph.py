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
import argparse, json
from typing import Dict, Any

from ..config import Config
from ..llm.vertex import get_vertex_chat_model
from ..agents.runner_agent import RunnerAgent
from ..agents.router_agent import RouterAgent
from ..agents.refiner_agent import RefinerAgent
from ..composite_agents.runner_router_refiner import RunnerRouterRefinerComposite
from ..schemas.io import SimpleOutput


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Run composite: Runner→Router→(Refiner).")
    parser.add_argument("--input", required=True, help="User input text.")
    parser.add_argument("--force_refine", action="store_true", help="Force routing to Refiner.")
    args = parser.parse_args(argv)

    # 1) Config & Vertex init
    cfg = Config.load()
    cfg.apply_google_env()
    cfg.init_vertex()

    # 2) Build LLMs and atomic agents (per-agent overrides via default.yaml)
    runner_llm  = get_vertex_chat_model(cfg, agent="runner")
    refiner_llm = get_vertex_chat_model(cfg, agent="refiner")

    runner  = RunnerAgent(runner_llm)
    router  = RouterAgent(require_exact="OK.")
    refiner = RefinerAgent(refiner_llm, requirements="The final output must be exactly 'OK.'")

    # 3) Compose
    composite = RunnerRouterRefinerComposite(runner, router, refiner)

    # 4) Execute
    state: Dict[str, Any] = {"user_input": args.input, "force_refine": args.force_refine}
    final_state = composite.invoke(state)

    # 5) Normalize & print
    out = SimpleOutput(text=final_state.get("text", ""))
    print(json.dumps(out.model_dump(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
