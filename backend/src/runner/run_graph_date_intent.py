'''
# 1) Ask for date → must return "<today> OK"
python -m src.runner.run_graph_date_intent --input "give me the date"

# 2) Not asking date, but exact OK -> PASS as usual
python -m src.runner.run_graph_date_intent --input "Say exactly: OK."

# 3) Not asking date, not OK -> go normal refiner branch
python -m src.runner.run_graph_date_intent --input "Say hi" --force_refine
'''
from __future__ import annotations
import argparse, json
from typing import Dict, Any

from ..config import Config
from ..llm.vertex import get_vertex_chat_model
from ..agents.runner_agent import RunnerAgent
from ..agents.router_agent import RouterAgent
from ..agents.refiner_agent import RefinerAgent
from ..composite_agents.runner_router_refiner_date_intent import RunnerRouterRefinerDateIntentComposite
from ..schemas.io import SimpleOutput


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Graph with date tool and intent-based date refine.")
    parser.add_argument("--input", required=True, help="User input text.")
    parser.add_argument("--force_refine", action="store_true", help="Force routing to Refiner (non-date).")
    args = parser.parse_args(argv)

    cfg = Config.load()
    cfg.apply_google_env()
    cfg.init_vertex()

    runner_llm  = get_vertex_chat_model(cfg, agent="runner")
    refiner_llm = get_vertex_chat_model(cfg, agent="refiner")

    runner  = RunnerAgent(runner_llm)
    router  = RouterAgent(require_exact="OK.")  # base rule
    refiner = RefinerAgent(refiner_llm, requirements="Keep intent; improve clarity only.")

    composite = RunnerRouterRefinerDateIntentComposite(runner, router, refiner)

    init: Dict[str, Any] = {"user_input": args.input, "force_refine": args.force_refine}
    final_state = composite.invoke(init)

    out = SimpleOutput(text=final_state.get("text", ""))
    print(json.dumps(out.model_dump(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
