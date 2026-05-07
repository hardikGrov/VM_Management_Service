from typing import Any

from pydantic import BaseModel, Field


class ErrorResponse(BaseModel):
    error: str = Field(description="Stable machine-readable error code.")
    message: str = Field(description="Human-readable error message.")
    details: dict[str, Any] | None = Field(
        default=None,
        description="Optional structured metadata.",
    )
