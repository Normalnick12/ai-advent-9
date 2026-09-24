"""Day 19 transport DTOs; evidence and verdicts are separate."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator


class CompositionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    prompt: str = Field(min_length=1, max_length=12000)

    @field_validator("prompt")
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError("prompt must not be blank")
        return value


class CompositionOperation(BaseModel):
    operation_id: str
    invocation: Literal["not_sent", "unknown", "observed", "not_observed"]
    outcome: str
    evidence_path: str | None = None
    evidence_saved: bool = False
    response_id: str | None = None
    provider_status: str | None = None
    final_text: str | None = None
    error_category: str | None = None
