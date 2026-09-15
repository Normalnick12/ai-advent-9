"""Typed behavioral preferences. No memory, provider or experiment dependencies."""
from typing import Annotated, Literal
from uuid import UUID

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, StringConstraints


def canonical_id(value: str) -> str:
    if str(UUID(value)) != value:
        raise ValueError("noncanonical identity")
    return value


Identity = Annotated[str, AfterValidator(canonical_id)]
Revision = Annotated[int, Field(ge=0)]


class ProfileError(Exception):
    def __init__(self, code: str, status: int = 409):
        self.code, self.status = code, status
        super().__init__(code)


class FrozenModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class SummaryBullets(FrozenModel):
    kind: Literal["summary_bullets"]
    max_bullets: int = Field(ge=1, le=5)


class TeachingSections(FrozenModel):
    kind: Literal["teaching_sections"]


class ProfileConstraints(FrozenModel):
    no_emoji: bool
    skip_basic_explanations: bool
    explain_unfamiliar_terms: bool


class ProfileFields(FrozenModel):
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]
    language: Literal["ru", "en"]
    tone: Literal["technical", "explanatory"]
    verbosity: Literal["concise", "detailed"]
    response_format: Annotated[SummaryBullets | TeachingSections, Field(discriminator="kind")]
    constraints: ProfileConstraints

    def behavior(self) -> dict:
        return {key: getattr(self, key) for key in ProfileFields.model_fields if key != "name"}


class AgentProfile(ProfileFields):
    profile_id: Identity
    owner_id: Identity
    revision: Revision


class ActiveProfileBinding(FrozenModel):
    owner_id: Identity
    active_profile_id: Identity | None = None
    revision: Revision = 0
