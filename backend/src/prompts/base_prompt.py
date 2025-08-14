from __future__ import annotations
from langchain_core.prompts import ChatPromptTemplate

# L0: Zero-system (default). Absolutely minimal; no style or modality bias.
BASE_PROMPT = ChatPromptTemplate.from_messages([
    ("user", "{user_input}")
])

# L1: Plain-neutral (optional). Tiny hint, still generic.
BASE_PLAIN_PROMPT = ChatPromptTemplate.from_messages([
    ("system", "You are a helpful assistant. Follow the user's instructions without adding extra content."),
    ("user", "{user_input}"),
])

# L2: Text-only (optional). If you explicitly want to suppress code unless asked.
BASE_TEXT_ONLY_PROMPT = ChatPromptTemplate.from_messages([
    ("system", "Respond in plain text. Do not include code or markdown code blocks unless explicitly requested."),
    ("user", "{user_input}"),
])
