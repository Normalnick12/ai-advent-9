"""Day 12 transport and controlled fixtures; not part of Profile domain."""
from typing import Literal
from pydantic import Field, field_validator

from app.llm_client import AgentConfig
from app.profiles import FrozenModel, Identity, ProfileFields, Revision
from app.profile_instructions import BASE_INSTRUCTIONS

CONFIG = AgentConfig(model="gpt-4o-mini", reasoning_effort=None, service_tier="default",
                     truncation="disabled", max_output_tokens=2000, text_format=None,
                     version="day12-v1", instructions=BASE_INSTRUCTIONS)
SEED = "Готов продолжить. Подтверди получение сообщения."
QUERY = ("Как организовать обработку loading/error/success для текущего экрана? "
         "Учти текущую задачу и выбранную архитектуру, назови проект и релиз.")
LONG = {"project_code": "ORION-17", "preferred_architecture": "MVVM"}
WORKING = {"task": "Checkout", "current_architecture": "MVI", "release_marker": "RC-42"}
FIXTURES = {
    "A": ProfileFields(name="Compact Engineer", language="ru", tone="technical", verbosity="concise",
        response_format={"kind": "summary_bullets", "max_bullets": 3},
        constraints={"no_emoji": True, "skip_basic_explanations": True, "explain_unfamiliar_terms": False}),
    "B": ProfileFields(name="Mentor", language="ru", tone="explanatory", verbosity="detailed",
        response_format={"kind": "teaching_sections"},
        constraints={"no_emoji": True, "skip_basic_explanations": False, "explain_unfamiliar_terms": True}),
}


class CreateProfile(FrozenModel):
    owner_id: Identity
    fields: ProfileFields


class EditProfile(CreateProfile):
    expected_revision: Revision


class SelectProfile(FrozenModel):
    owner_id: Identity
    expected_profile_revision: Revision
    expected_binding_revision: Revision


class RequestSnapshot(FrozenModel):
    snapshot_id: str = Field(pattern=r"^[a-f0-9]{64}$")
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


class FreezeRequest(RequestSnapshot):
    profile_a_id: Identity
    profile_a_revision: Revision
    profile_b_id: Identity
    profile_b_revision: Revision


class ProbeRequest(RequestSnapshot):
    comparison_id: Identity
    slot: Literal["A", "B"]
