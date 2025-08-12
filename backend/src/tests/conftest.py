# tests/conftest.py
from __future__ import annotations
import os
import pytest

from langchain_core.language_models.fake_chat_models import FakeListChatModel

# ---- Global switch: use real LLM? ----
@pytest.fixture(scope="session")
def use_real_llm() -> bool:
    return os.getenv("TEST_USE_REAL_LLM", "false").lower() == "true"

@pytest.fixture(scope="session")
def assertions_enabled(use_real_llm: bool) -> bool:
    # When real LLM is used, we avoid strict assertions.
    return not use_real_llm

# ---- Fake LLM factory ----
@pytest.fixture
def fake_llm_factory():
    """
    Usage:
        llm = fake_llm_factory(["hello", "world"])
    This cycles responses in order.
    """
    def _make(responses):
        return FakeListChatModel(responses=responses)
    return _make
