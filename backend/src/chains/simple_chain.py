# src/chains/simple_chain.py
'''
input: a dict {"user_input": str}.

flow: BASE_PROMPT (system+user) → ChatVertexAI → StrOutputParser.

output: plain str.
'''

from __future__ import annotations

from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import Runnable

from ..prompts.base_prompt import BASE_PROMPT


def build_simple_chain(model) -> Runnable:
    """
    Minimal LCEL chain: prompt -> model -> string.
    Input dict must contain {"user_input": "..."}.
    """
    parser = StrOutputParser()
    chain = BASE_PROMPT | model | parser
    return chain
