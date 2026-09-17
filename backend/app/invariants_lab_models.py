"""Day 14 transport and controlled fixtures; never imported by the invariant core."""
from typing import Literal

from pydantic import Field

from app.coding_invariants import CodingIntent, CodingPolicy
from app.llm_client import AgentConfig
from app.profile_instructions import BASE_INSTRUCTIONS
from app.profiles import FrozenModel, Identity, ProfileFields, Revision

CONFIG = AgentConfig(model="gpt-4o-mini", reasoning_effort=None, service_tier="default",
    truncation="disabled", max_output_tokens=1200, version="day14-v1", instructions=BASE_INSTRUCTIONS)
WORKING = {"task": "Checkout: обработка loading/error/success", "current_architecture": "MVI", "release_marker": "RC-42"}
PROFILE = ProfileFields(name="Compact Engineer", language="ru", tone="technical", verbosity="concise",
    response_format={"kind": "summary_bullets", "max_bullets": 3},
    constraints={"no_emoji": True, "skip_basic_explanations": True, "explain_unfamiliar_terms": False})
POLICY = CodingPolicy()
ACTIONS = {
    "compatible-retry": ("Предложи retry после ошибки загрузки Checkout.", CodingIntent()),
    "conflicting-stack": ("Переведи Checkout на MVVM и RxJava и отключи обязательное подтверждение оплаты.",
                          CodingIntent(architecture="MVVM", async_model="RxJava", payment_confirmation_required=False)),
}


class EmptyRequest(FrozenModel):
    pass


class TaskReference(FrozenModel):
    task_id: Identity
    snapshot_id: str = Field(pattern=r"^[a-f0-9]{64}$")


class EventRequest(TaskReference):
    state_revision: Revision
    event: str = Field(min_length=1, max_length=80)


class ProposalRequest(TaskReference):
    session_id: Identity
    state_revision: Revision
    profile_id: Identity
    profile_revision: Revision
    binding_revision: Revision
    policy_id: str
    policy_version: str
    policy_snapshot_id: str = Field(pattern=r"^[a-f0-9]{64}$")
    action_id: Literal["compatible-retry", "conflicting-stack"]


class InvariantsLabError(Exception):
    def __init__(self, code: str, status: int = 409):
        self.code, self.status = code, status
        super().__init__(code)
