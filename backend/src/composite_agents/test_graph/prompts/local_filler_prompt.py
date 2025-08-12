from __future__ import annotations
from langchain_core.prompts import ChatPromptTemplate

# A composite-local prompt (not in the global registry) to demonstrate
# "local prompt" usage inside this composite only.
#
# Goal: given six letters, produce a tiny playful label mentioning them.
LOCAL_FILLER_PROMPT = ChatPromptTemplate.from_messages(
    [
        ("system",
         "You craft a short playful label that mentions the given letters. "
         "Keep it on one line, <= 8 words, and do not add extra punctuation."),
        ("user", "Letters: {letters}\nCreate a short label:"),
    ]
)
