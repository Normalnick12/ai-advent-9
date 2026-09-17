"""Structured generation and strict parsing live here, outside invariant enforcement."""
from dataclasses import asdict, replace
import json

from app.agent import SimpleAgent
from app.coding_invariants import CodingProposal
from app.validated_turn import CandidateGeneration


def parse_candidate(text: str) -> CodingProposal:
    def unique(pairs):
        values = {}
        for key, value in pairs:
            if key in values:
                raise ValueError("duplicate key")
            values[key] = value
        return values
    return CodingProposal.model_validate(json.loads(text, object_pairs_hook=unique))


class CodingCandidateAdapter:
    def __init__(self, client, prepared):
        self.config = replace(prepared.config, text_format={
            "type": "json_schema", "name": "coding_proposal", "strict": True,
            "schema": CodingProposal.model_json_schema(),
        }, instructions=prepared.config.instructions +
            "\nReturn a coding proposal using the response schema. Choose a retry mode for loading only. "
            "The application validates the proposal and renders the final answer. Do not add prose or code.")
        self.agent = SimpleAgent(client, self.config)
        self.messages = prepared.messages
        self.outcome = None
        self.candidate = None
        self.preparation = "not_attempted"

    async def generate(self):
        outcome = await self.agent.generate(self.messages)
        self.outcome = asdict(outcome)
        if outcome.status != "completed":
            self.preparation = "unavailable"
            return CandidateGeneration(error_code=outcome.error_code or "provider_" + outcome.status)
        try:
            self.candidate = parse_candidate(outcome.reply)
        except (ValueError, TypeError):
            self.preparation = "error"
            return CandidateGeneration(error_code="invalid_candidate")
        self.preparation = "parsed"
        return CandidateGeneration(candidate=self.candidate)
