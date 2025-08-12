from __future__ import annotations
from langchain_core.prompts import ChatPromptTemplate

LLM_ROUTER_PROMPT = ChatPromptTemplate.from_messages(
    [
        ("system",
         "You are a strict router. Decide the route.\n"
         "Return ONLY one of these tokens: PASS, REFINE, REFINE_DATE.\n\n"
         "Guidelines:\n"
         "- If the user asks for today's date (explicitly or implicitly), choose REFINE_DATE.\n"
         "- If the draft already perfectly fits the user request, choose PASS.\n"
         "- Otherwise choose REFINE.\n"
         "No explanations."),
        ("user", "User input:\n{user_input}\n\nDraft:\n{draft}\n\nRoute:")
    ]
)
