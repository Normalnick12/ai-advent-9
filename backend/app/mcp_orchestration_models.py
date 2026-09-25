"""Day 20 transport types; native evidence lives in the local attempt directory."""
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class OrchestrationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    prompt: str = Field(min_length=1, max_length=12000)

    @field_validator("prompt")
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError("Prompt must not be blank")
        return value


class OrchestrationOperation(BaseModel):
    operation_id: str
    outcome: str
    invocation: Literal["not_sent", "unknown", "observed", "not_observed"] = "not_sent"
    evidence_path: str | None = None
    provider_status: str | None = None
    response_id: str | None = None
    final_text: str | None = None
    error_category: str | None = None
