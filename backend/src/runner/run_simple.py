from __future__ import annotations

import argparse
import json
import sys

from ..config import Config
from ..llm.vertex import get_vertex_chat_model
from ..chains.simple_chain import build_simple_chain
from ..schemas.io import SimpleInput, SimpleOutput


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Run a minimal LangChain chain on Vertex AI (local client)."
    )
    parser.add_argument(
        "--input",
        required=True,
        help="User input text (quoted). Example: --input 'Summarize: attention is all you need.'",
    )
    args = parser.parse_args(argv)

    # 1) Config & credentials
    cfg = Config()
    cfg.apply_google_credentials()

    # 2) Model
    model = get_vertex_chat_model(cfg)

    # 3) Chain
    chain = build_simple_chain(model)

    # 4) Validate input
    inp = SimpleInput(user_input=args.input)

    # 5) Invoke
    text = chain.invoke(inp.model_dump())
    print(f"[DEBUG] Raw text repr: {text!r}", file=sys.stderr)
    
    # 6) Validate & print output as JSON (easy to pipe)
    out = SimpleOutput(text=text)
    print(json.dumps(out.model_dump(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
