"""Day 13 transport and demo data, separate from reusable FSM contracts."""
from typing import Literal
from pydantic import Field, field_validator
from app.llm_client import AgentConfig
from app.profile_instructions import BASE_INSTRUCTIONS
from app.profiles import FrozenModel, Identity, ProfileFields, Revision

CONFIG = AgentConfig(model="gpt-4o-mini", reasoning_effort=None, service_tier="default",
    truncation="disabled", max_output_tokens=2000, version="day13-v1", instructions=BASE_INSTRUCTIONS)
WORKING = {"task": "Checkout: обработка loading/error/success", "current_architecture": "MVI", "release_marker": "RC-42"}
PROFILE = ProfileFields(name="Compact Engineer", language="ru", tone="technical", verbosity="concise",
    response_format={"kind": "summary_bullets", "max_bullets": 3},
    constraints={"no_emoji": True, "skip_basic_explanations": True, "explain_unfamiliar_terms": False})
QUERY = "Что делать дальше?"
EXECUTION_QUERY = "Покажи следующий небольшой шаг реализации текущей задачи."


class TaskReference(FrozenModel):
    snapshot_id: str = Field(pattern=r"^[a-f0-9]{64}$")
    task_id: Identity


class InitializeState(TaskReference):
    machine_id: Literal["checkout-v1"]


class StateReference(TaskReference):
    state_revision: Revision


class ApplyEvent(StateReference):
    event: str = Field(min_length=1, max_length=80)


class RequestSnapshot(StateReference):
    profile_id: Identity
    profile_revision: Revision
    binding_revision: Revision


class SendRequest(RequestSnapshot):
    message: str = Field(min_length=1, max_length=20000)

    @field_validator("message")
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError("blank message")
        return value


class CreateProfile(FrozenModel):
    owner_id: Identity
    fields: ProfileFields


class EditProfile(CreateProfile):
    expected_revision: Revision


class SelectProfile(FrozenModel):
    owner_id: Identity
    expected_profile_revision: Revision
    expected_binding_revision: Revision
