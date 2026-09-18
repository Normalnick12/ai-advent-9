"""Concrete, versioned Coding composition values and bounded conversation generation."""
from dataclasses import asdict, replace
import json
from typing import Literal

from pydantic import Field, field_validator

from app.agent import SimpleAgent
from app.coding_invariants import CodingDecisions, CodingModel, CodingPolicy
from app.llm_client import AgentConfig
from app.profile_instructions import BASE_INSTRUCTIONS
from app.profiles import ProfileFields
from app.validated_turn import CandidateGeneration
from app.playground_workflow import CHECKOUT_V2, EVENT_LABELS, NODE_LABELS

TASK_TITLE = "Checkout: loading/error/success + retry"
CONFIG = AgentConfig(model="gpt-5.6", reasoning_effort="none", service_tier="default",
    truncation="disabled", max_output_tokens=2400, version="day15-v1", instructions=BASE_INSTRUCTIONS)
PROFILE_PRESETS = {
    "compact": ProfileFields(name="Compact Engineer", language="ru", tone="technical", verbosity="concise",
        response_format={"kind": "summary_bullets", "max_bullets": 3},
        constraints={"no_emoji": True, "skip_basic_explanations": True, "explain_unfamiliar_terms": False}),
    "mentor": ProfileFields(name="Mentor", language="ru", tone="explanatory", verbosity="detailed",
        response_format={"kind": "teaching_sections"},
        constraints={"no_emoji": True, "skip_basic_explanations": False, "explain_unfamiliar_terms": True}),
}
BOUNDED_COVERAGE = {
    "decisions": ("architecture", "ui_toolkit", "async_model", "payment_confirmation_required"),
    "answer_structure": "checked", "prose_semantics": "not_checked", "code_execution": "not_attempted",
}


class CodingTaskConfiguration(CodingModel):
    version: Literal["coding-setup-v1"] = "coding-setup-v1"
    preset: Literal["checkout"] = "checkout"
    profile_preset: Literal["compact", "mentor"] = "compact"
    policy: CodingPolicy = Field(default_factory=CodingPolicy)


class CodingTurn(CodingModel):
    version: Literal["coding-turn-v1"]
    answer: str = Field(min_length=1, max_length=20000)
    decisions: CodingDecisions

    @field_validator("answer")
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError("blank answer")
        return value


def catalog():
    return {
        "task_title": TASK_TITLE, "machine_id": CHECKOUT_V2.machine_id,
        "defaults": CodingTaskConfiguration().model_dump(),
        "profiles": [{"id": key, "name": value.name} for key, value in PROFILE_PRESETS.items()],
        "policy_options": {"required_architecture": ["MVI", "MVVM"],
            "required_ui_toolkit": ["Compose", "Views"],
            "required_async_model": ["CoroutinesFlow", "RxJava"],
            "payment_confirmation_required": [True, False]},
        "nodes": NODE_LABELS, "event_labels": EVENT_LABELS,
    }


def parse_turn(text: str) -> CodingTurn:
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate key")
            result[key] = value
        return result
    return CodingTurn.model_validate(json.loads(text, object_pairs_hook=unique))


def render_turn(candidate: CodingTurn) -> str:
    return candidate.answer


class ConversationCandidateAdapter:
    def __init__(self, client, prepared):
        self.config = replace(prepared.config, text_format={
            "type": "json_schema", "name": "coding_turn", "strict": True,
            "schema": CodingTurn.model_json_schema(),
        }, instructions=prepared.config.instructions +
            "\nReturn coding-turn-v1 with a natural answer to the user's query and all four coding decisions. "
            "Discuss requirements, plans, implementation or validation as appropriate to the current task. "
            "The application checks the declared decisions, not the semantics of prose/code. "
            "Do not claim to execute code, tests, or lifecycle events. Task progress and recovery require explicit user controls.")
        self.agent = SimpleAgent(client, self.config)
        self.messages = prepared.messages
        self.outcome = self.candidate = None
        self.preparation = "not_attempted"

    async def generate(self):
        outcome = await self.agent.generate(self.messages)
        self.outcome = asdict(outcome)
        if outcome.status != "completed":
            self.preparation = "unavailable"
            return CandidateGeneration(error_code=outcome.error_code or "provider_" + outcome.status)
        try:
            self.candidate = parse_turn(outcome.reply)
        except (ValueError, TypeError):
            self.preparation = "error"
            return CandidateGeneration(error_code="invalid_candidate")
        self.preparation = "parsed"
        return CandidateGeneration(candidate=self.candidate)
