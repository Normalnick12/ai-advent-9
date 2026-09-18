"""Strict Playground transport. Current references are never model-provided."""
from typing import Literal

from pydantic import Field, field_validator

from app.profiles import FrozenModel, Identity, Revision
from app.playground_coding import CodingTaskConfiguration


class PlaygroundError(Exception):
    def __init__(self, code, status=409):
        self.code, self.status = code, status
        super().__init__(code)


class TaskReference(FrozenModel):
    task_id: Identity
    session_id: Identity
    snapshot_id: str = Field(pattern=r"^[a-f0-9]{64}$")


class SourceReference(TaskReference):
    state_revision: Revision
    profile_id: Identity
    profile_revision: Revision
    binding_revision: Revision
    policy_id: str
    policy_version: str
    policy_snapshot_id: str = Field(pattern=r"^[a-f0-9]{64}$")


class SendRequest(SourceReference):
    query: str = Field(min_length=1, max_length=20000)

    @field_validator("query")
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError("blank query")
        return value


class EventRequest(TaskReference):
    state_revision: Revision
    event: str = Field(pattern=r"^[A-Z][A-Z0-9_]{0,79}$")


class CreateRequest(FrozenModel):
    configuration: CodingTaskConfiguration
    current: SourceReference | None = None


class CompleteSetupRequest(FrozenModel):
    task_id: Identity


class ProfileRequest(SourceReference):
    profile_preset: Literal["compact", "mentor"]
