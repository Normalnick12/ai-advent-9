from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StrictStr, field_validator


class CreateSessionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AgentMessageRequest(CreateSessionRequest):
    message: StrictStr = Field(min_length=1, max_length=20000)

    @field_validator("message")
    @classmethod
    def nonblank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("blank")
        return value


class AgentError(BaseModel):
    code: str
    message: str


class SessionResponse(BaseModel):
    session_id: UUID
    history_turn_count: int


class AgentTurnResponse(SessionResponse):
    request_id: str
    status: Literal["completed", "incomplete", "refused", "error"]
    reply: str | None
    incomplete_reason: str | None
    error: AgentError | None
