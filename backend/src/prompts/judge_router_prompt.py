"""
This prompt is intentionally NOT used by the MVP router, which is rule-based.
It documents what "pass" means so we can later swap to LLM judging if needed.

Rule for PASS (deterministic in router_agent.py):
- Output must equal the string 'OK.' exactly (strip() == 'OK.')
- This makes local testing trivial via: --input "Say exactly: OK."

If you later want LLM-driven judging, you can import this template.
"""
from langchain_core.prompts import ChatPromptTemplate

JUDGE_ROUTER_PROMPT = ChatPromptTemplate.from_messages(
    [
        ("system",
         "You judge if a text meets strict criteria. "
         "Return only 'PASS' or 'REFINE'. Criteria: the text must be exactly 'OK.'."),
        ("user", "Text to judge:\n\n{draft_text}\n\nReturn PASS or REFINE only."),
    ]
)