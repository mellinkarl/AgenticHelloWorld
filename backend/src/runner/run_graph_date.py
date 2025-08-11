'''
# PASS path (exact OK.)
python -m src.runner.run_graph_date --input "Say exactly: OK."

# Force REFINE path → output must differ from draft; if unchanged by LLM, date is appended
python -m src.runner.run_graph_date --input "Say: hi" --force_refine
'''

from __future__ import annotations
import argparse, json
from typing import Dict, Any

from ..config import Config
from ..llm.vertex import get_vertex_chat_model
from ..agents.runner_agent import RunnerAgent
from ..agents.router_agent import RouterAgent
from ..agents.refiner_agent import RefinerAgent
from ..composite_agents.runner_router_refiner_with_date import RunnerRouterRefinerWithDateComposite
from ..schemas.io import SimpleOutput


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Run Runner→Router→(Refiner) with date tool and ensure-diff.")
    parser.add_argument("--input", required=True, help="User input text.")
    parser.add_argument("--force_refine", action="store_true", help="Force routing to Refiner.")
    args = parser.parse_args(argv)

    cfg = Config.load()
    cfg.apply_google_env()
    cfg.init_vertex()

    # Build per-agent LLMs (can override via default.yaml)
    runner_llm  = get_vertex_chat_model(cfg, agent="runner")
    refiner_llm = get_vertex_chat_model(cfg, agent="refiner")

    runner  = RunnerAgent(runner_llm)
    router  = RouterAgent(require_exact="OK.")  # same rule
    refiner = RefinerAgent(refiner_llm, requirements="Rephrase to improve clarity without changing meaning.")

    composite = RunnerRouterRefinerWithDateComposite(runner, router, refiner)

    init: Dict[str, Any] = {"user_input": args.input, "force_refine": args.force_refine}
    final_state = composite.invoke(init)

    out = SimpleOutput(text=final_state.get("text", ""))
    print(json.dumps(out.model_dump(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
