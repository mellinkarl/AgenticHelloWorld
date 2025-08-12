from __future__ import annotations
import argparse, json
from ..config import Config, init_logging, get_logger
from ..composite_agents.test_linear.composite import TestLinearComposite
from ..schemas.io import SimpleOutput

log = get_logger(__name__)

def main(argv=None) -> int:
    cfg = Config.load()
    init_logging(cfg)  # <<< initialize logging early
    parser = argparse.ArgumentParser(description="Run the linear test composite with universal agents.")
    parser.add_argument("--input", required=True, help="User input text.")
    args = parser.parse_args(argv)

    log.info("Starting composite test")
    comp = TestLinearComposite()
    final = comp.invoke({"user_input": args.input})
    log.info("Completed composite test")

    out = SimpleOutput(text=final.get("text", ""))
    print(json.dumps(out.model_dump(), ensure_ascii=False, indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
