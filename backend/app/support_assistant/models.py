"""Boundary models shared by the HTTP service and the ticket MCP server."""
from datetime import datetime, timezone
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

TicketId = Annotated[str, Field(pattern=r'^T-[0-9]{3}$')]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)


def utc(value):
    parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise ValueError('timestamp_must_be_utc')
    return parsed


class SupportRequest(StrictModel):
    ticket_id: TicketId
    question: str = Field(min_length=1, max_length=4000)

    @field_validator('question')
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError('question_must_be_nonblank')
        return value


class Observations(StrictModel):
    account_status: Literal['temporarily_locked', 'active'] | None = None
    error_code: Literal['AUTH_TEMP_LOCK', 'VERIFICATION_CODE_EXPIRED'] | None = None
    verification_status: Literal['expired'] | None = None
    failed_attempts: int | None = Field(default=None, ge=0)
    blocked_until: str | None = None

    @field_validator('blocked_until')
    @classmethod
    def timestamp(cls, value):
        if value is not None:
            utc(value)
        return value


class Ticket(StrictModel):
    ticket_id: TicketId
    message: str = Field(min_length=1, max_length=4000)
    observations: Observations


class DemoData(StrictModel):
    schema_version: Literal[1]
    snapshot_at: str
    tickets: list[Ticket]

    @model_validator(mode='after')
    def consistent(self):
        snapshot = utc(self.snapshot_at)
        if not self.tickets or len({t.ticket_id for t in self.tickets}) != len(self.tickets):
            raise ValueError('invalid_ticket_ids')
        for ticket in self.tickets:
            until = ticket.observations.blocked_until
            if until and utc(until) <= snapshot:
                raise ValueError('block_must_end_after_snapshot')
        return self


class TicketResult(StrictModel):
    status: Literal['found', 'not_found']
    ticket_id: TicketId
    snapshot_at: str
    ticket: Ticket | None
    call_id: str
    server_pid: int = Field(gt=0)

    @model_validator(mode='after')
    def consistent(self):
        utc(self.snapshot_at)
        UUID(self.call_id)
        if (self.status == 'found') != (self.ticket is not None):
            raise ValueError('invalid_ticket_result')
        if self.ticket and self.ticket.ticket_id != self.ticket_id:
            raise ValueError('ticket_id_mismatch')
        return self


class Candidate(StrictModel):
    status: Literal['answered', 'insufficient_context']
    answer: str
    cause: Literal['temporary_lock', 'expired_code', 'unknown', 'not_applicable']
    faq_evidence_ids: list[str]
    ticket_fact_ids: list[str]
    clarifying_questions: list[str]


class SupportFailure(Exception):
    def __init__(self, code, trace, *, detail=None):
        self.code, self.trace, self.detail = code, trace, detail
        super().__init__(code)
