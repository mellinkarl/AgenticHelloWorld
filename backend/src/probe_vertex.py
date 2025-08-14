# src/probe_vertex.py
# Usage:
#   python -m src.probe_vertex           # Only probe env/libs, no LLM call
#   python -m src.probe_vertex --call    # Probe + actual LLM test call

from __future__ import annotations

import os
import sys
import traceback
import argparse

import vertexai
from google.auth.exceptions import DefaultCredentialsError
from langchain_google_vertexai import ChatVertexAI

from .config.config import Config


def print_env_probe(cfg: Config) -> None:
    """Print useful environment & library diagnostics."""
    print("=== Vertex Probe ===")
    print(f"Config source     : {cfg._source}")
    print(f"USE_ADC           : {cfg.use_adc}")
    print(f"Project           : {cfg.project}")
    print(f"Location          : {cfg.location}")
    print(f"Default Model     : {cfg.llm.model_name}")
    print(f"GOOGLE_APPLICATION_CREDENTIALS: {os.getenv('GOOGLE_APPLICATION_CREDENTIALS')}")
    try:
        import langchain, langchain_google_vertexai, google.cloud.aiplatform as aiplatform
        print(f"LangChain                 : {getattr(langchain, '__version__', 'unknown')}")
        print(f"langchain-google-vertexai : {getattr(langchain_google_vertexai, '__version__', 'unknown')}")
        print(f"google-cloud-aiplatform   : {getattr(aiplatform, '__version__', 'unknown')}")
    except Exception as e:
        print(f"[warn] Version probe failed: {e}")


def build_llm(cfg: Config) -> ChatVertexAI:
    """Build ChatVertexAI without triggering a request."""
    cfg.apply_google_env()
    cfg.init_vertex()
    credentials = cfg.load_credentials() if not cfg.use_adc else None
    return ChatVertexAI(credentials=credentials, **cfg.llm_kwargs())


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Probe Vertex AI environment; optional --call to test an actual LLM request."
    )
    parser.add_argument("--call", action="store_true", help="Actually call the LLM for a test message.")
    args = parser.parse_args(argv)

    try:
        cfg = Config.load()
    except Exception as e:
        print("STATUS: FAILED (Config load error)")
        traceback.print_exc()
        return 1

    print_env_probe(cfg)

    try:
        llm = build_llm(cfg)
        if args.call:
            msg = llm.invoke("Return literally: OK.")
            print("---- LLM Response ----")
            print("CONTENT:", repr(getattr(msg, "content", None)))
            print("RAW:", msg)
            print("STATUS: SUCCESS")
        else:
            print("STATUS: SKIPPED (no LLM call; use --call to test actual output)")
        return 0
    except DefaultCredentialsError as e:
        print("STATUS: FAILED (DefaultCredentialsError)")
        print(e)
        return 2
    except Exception:
        print("STATUS: FAILED (Exception)")
        traceback.print_exc()
        return 3


if __name__ == "__main__":
    sys.exit(main())
