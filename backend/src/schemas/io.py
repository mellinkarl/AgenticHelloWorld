from __future__ import annotations

from pydantic import BaseModel, Field


class SimpleInput(BaseModel):
    """Validated input to the simple chain."""
    user_input: str = Field(..., description="Natural language user query")


class SimpleOutput(BaseModel):
    """Validated output from the simple chain."""
    text: str = Field(..., description="Model's plain text response")
