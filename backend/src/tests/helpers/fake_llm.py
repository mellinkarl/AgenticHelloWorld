# tests/helpers/fake_llm.py
from typing import Sequence
from langchain_core.language_models.fake_chat_models import FakeListChatModel
from langchain_core.messages import AIMessage

def make_fake_llm(responses: Sequence[str]) -> FakeListChatModel:
    """
    Create a FakeListChatModel that cycles through the given responses.

    Example:
        responses = ["A", "B"]
        Call #1 -> "A"
        Call #2 -> "B"
        Call #3 -> "A" (wraps around)
    """
    return FakeListChatModel(responses=list(responses))

def get_llm(mode: str, real_llm_factory):
    """
    Factory method to get either a fake or real LLM instance.

    Args:
        mode: "fake" or "real".
        real_llm_factory: A callable that returns a real LLM instance
            (e.g., your project's `get_vertex_chat_model`).

    Returns:
        FakeListChatModel if mode == "fake",
        otherwise the result of real_llm_factory().
    """
    if mode == "fake":
        # Provide a default short list of responses for testing.
        # Individual test cases can override this by calling make_fake_llm(...)
        return make_fake_llm(["OK.", "PASS", "Refined text."])
    return real_llm_factory()

