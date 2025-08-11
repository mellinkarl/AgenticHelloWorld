# src/runner/run_simple.py
'''
# Option A: explicit key from default.yaml (your current setup)
python -m src.runner.run_simple --input "Say exactly: OK."

# Option B: ADC (if you prefer)
USE_ADC=true python -m src.runner.run_simple --input "Say exactly: OK."
# (Ensure ADC is actually available on this machine/user)
'''

from __future__ import annotations
import argparse, json, sys
from ..config import Config
from ..llm.vertex import get_vertex_chat_model
from ..chains.simple_chain import build_simple_chain
from ..schemas.io import SimpleInput, SimpleOutput

def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Run a minimal LangChain chain on Vertex AI (local client).")
    parser.add_argument("--input", required=True, help="User input text (quoted).")
    args = parser.parse_args(argv)

    # 1) Config & credentials
    cfg = Config.load()
    cfg.apply_google_env()
    cfg.init_vertex()

    # 2) Model
    model = get_vertex_chat_model(cfg, agent="runner")

    # 3) Chain
    chain = build_simple_chain(model)

    # 4) Validate input
    inp = SimpleInput(user_input=args.input)

    # 5) Invoke
    text = chain.invoke(inp.model_dump())
    print(f"[DEBUG] Raw text repr: {text!r}", file=sys.stderr)

    # 6) Output as JSON
    out = SimpleOutput(text=text)
    print(json.dumps(out.model_dump(), ensure_ascii=False, indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
