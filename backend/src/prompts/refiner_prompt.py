from __future__ import annotations

from langchain_core.prompts import ChatPromptTemplate

# "Do not change intent" refiner. It only fixes format/clarity/required fields.
REFINER_SYSTEM = (
    "You refine a short draft WITHOUT changing its meaning. "
    "Only fix formatting, clarity, and minimal completion if criteria are unmet. "
    "Never invent facts. Keep it concise."
)

REFINER_PROMPT = ChatPromptTemplate.from_messages(
    [
        ("system", REFINER_SYSTEM),
        ("user",
         "Original draft:\n{draft_text}\n\n"
         "Requirements:\n{requirements}\n\n"
         "Rewrite the text to satisfy the requirements while preserving intent. "
         "Return plain text only."),
    ]
)
