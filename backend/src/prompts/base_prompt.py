from __future__ import annotations

from langchain_core.prompts import ChatPromptTemplate

# A minimal, general-purpose prompt. Keep it tiny & documented.
BASE_PROMPT = ChatPromptTemplate.from_messages(
    [
        ("system",
         "You are a concise, helpful assistant. "
         "Answer clearly. If the user asks for code, return minimal, runnable code."),
        ("user", "{user_input}"),
    ]
)
