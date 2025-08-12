'''
cmd: # Linear demo composite; stderr prints each step's snapshot
python -m src.runner.run_composite_test --input "Please say exactly: OK."
python -m src.runner.run_composite_test --input "Please say one ramdom sentence."
'''
from __future__ import annotations
import argparse, json

from ..config import Config
from ..llm.vertex import get_vertex_chat_model
from ..composite_agents.test_linear.composite import TestLinearComposite
from ..schemas.io import SimpleOutput

def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Run the linear test composite with universal agents.")
    parser.add_argument("--input", required=True, help="User input text.")
    args = parser.parse_args(argv)

    # --- use your existing config.py end-to-end ---
    cfg = Config.load()
    cfg.apply_google_env()
    cfg.init_vertex()

    # Per-agent LLMs (overrides can live in default.yaml -> agents.{runner,decider,refiner})
    runner_llm  = get_vertex_chat_model(cfg, agent="runner")
    decider_llm = get_vertex_chat_model(cfg, agent="decider")
    refiner_llm = get_vertex_chat_model(cfg, agent="refiner")

    comp = TestLinearComposite(
        runner_llm=runner_llm,
        decider_llm=decider_llm,
        refiner_llm=refiner_llm,
    )
    final = comp.invoke({"user_input": args.input})

    out = SimpleOutput(text=final.get("text", ""))
    print(json.dumps(out.model_dump(), ensure_ascii=False, indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
