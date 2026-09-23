"""Day 18 transport DTOs. Typed remote facts remain separate from model prose."""
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_validator


class WatchRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=12000)
    operation: Literal["create", "summary"]
    watch_id: UUID | None = None

    @model_validator(mode="after")
    def valid(self):
        if not self.prompt.strip() or (self.operation == "summary" and self.watch_id is None):
            raise ValueError("Nonblank prompt and selected summary watch required")
        if self.operation == "create" and self.watch_id is not None:
            raise ValueError("Create has no existing watch ID")
        return self


class Frozen(BaseModel):
    model_config = ConfigDict(frozen=True)

    @model_validator(mode="after")
    def utc_dates(self):
        for name in type(self).model_fields:
            value = getattr(self, name)
            if isinstance(value, datetime) and (value.utcoffset() is None or value.utcoffset().total_seconds() != 0):
                raise ValueError("UTC required")
        return self


class WatchReceipt(Frozen):
    watch_id: UUID
    group_id: str = Field(pattern=r"^[A-Za-z0-9_][A-Za-z0-9_-]*(?:\.[A-Za-z0-9_][A-Za-z0-9_-]*)*$")
    artifact_id: str = Field(pattern=r"^[A-Za-z0-9_][A-Za-z0-9_.-]*$")
    interval_seconds: int = Field(strict=True, ge=30, le=86400)
    max_runs: int = Field(strict=True, ge=1, le=100)
    created_at: datetime
    next_run_at: datetime | None
    status: Literal["active", "completed"]
    runs_total: int = Field(strict=True, ge=0)
    skipped_slots: int = Field(strict=True, ge=0)

    @model_validator(mode="after")
    def consistent(self):
        if self.runs_total > self.max_runs or ((self.status == "completed") != (self.runs_total == self.max_runs)):
            raise ValueError("Invalid watch budget/status")
        if (self.status == "completed") != (self.next_run_at is None):
            raise ValueError("Invalid next run")
        for time in (self.created_at, self.next_run_at):
            if time is not None and (time.utcoffset() is None or time.utcoffset().total_seconds() != 0):
                raise ValueError("UTC required")
        return self


class WatchExecution(Frozen):
    run_id: UUID
    watch_id: UUID
    scheduled_at: datetime
    started_at: datetime
    completed_at: datetime | None
    checked_at: datetime | None
    state: Literal["running", "succeeded", "failed"]
    lookup_outcome: Literal["found", "no_versions", "group_not_found", "artifact_not_found"] | None
    lookup_id: UUID | None
    source_url: str
    version_count: int | None = Field(ge=0)
    error_category: str | None

    @model_validator(mode="after")
    def execution_consistent(self):
        if (self.state == "running") != (self.completed_at is None):
            raise ValueError("Invalid execution terminal time")
        if self.state == "succeeded":
            if self.lookup_outcome is None or self.lookup_id is None or self.checked_at is None or self.error_category is not None:
                raise ValueError("Incomplete successful lookup")
            if self.version_count is None or ((self.lookup_outcome == "found") != (self.version_count > 0)):
                raise ValueError("Invalid version count")
        elif self.lookup_outcome is not None or self.version_count is not None:
            raise ValueError("Non-successful snapshot")
        if self.state == "failed" and self.error_category is None:
            raise ValueError("Missing failure category")
        if self.error_category == "interrupted" and (self.checked_at is not None or self.lookup_id is not None):
            raise ValueError("Interrupted outcome is unknown")
        return self


class WatchSummary(WatchReceipt):
    successful: int = Field(strict=True, ge=0)
    failed: int = Field(strict=True, ge=0)
    interrupted: int = Field(strict=True, ge=0)
    comparable_snapshots: int = Field(strict=True, ge=0)
    first_checked_at: datetime | None
    last_checked_at: datetime | None
    first_version_count: int | None = Field(ge=0)
    last_version_count: int | None = Field(ge=0)
    changes_detected: int = Field(strict=True, ge=0)
    newly_seen_versions: list[str]
    latest_execution: WatchExecution | None
    through_execution_id: UUID | None
    generated_at: datetime
    executions: list[WatchExecution]
    running_execution: WatchExecution | None

    @model_validator(mode="after")
    def aggregate_consistent(self):
        if self.runs_total != self.successful + self.failed or self.interrupted > self.failed:
            raise ValueError("Invalid aggregate counts")
        if self.comparable_snapshots > self.successful or len(self.executions) != self.runs_total:
            raise ValueError("Invalid snapshot count")
        if bool(self.runs_total) != bool(self.latest_execution):
            raise ValueError("Invalid latest execution")
        if self.through_execution_id != (self.latest_execution.run_id if self.latest_execution else None):
            raise ValueError("Invalid through execution")
        if self.executions and self.executions[-1] != self.latest_execution:
            raise ValueError("Latest is not terminal tail")
        expected = f"https://dl.google.com/dl/android/maven2/{self.group_id.replace('.', '/')}/group-index.xml"
        for run in [*self.executions, *([self.running_execution] if self.running_execution else [])]:
            if run.watch_id != self.watch_id or run.source_url != expected:
                raise ValueError("Execution identity mismatch")
        if any(run.state == "running" for run in self.executions):
            raise ValueError("Nonterminal aggregate")
        counts = (sum(r.state == "succeeded" for r in self.executions),
                  sum(r.state == "failed" for r in self.executions),
                  sum(r.error_category == "interrupted" for r in self.executions),
                  sum(r.lookup_outcome in ("found", "no_versions") for r in self.executions))
        if counts != (self.successful, self.failed, self.interrupted, self.comparable_snapshots):
            raise ValueError("Aggregate disagrees with execution history")
        if self.running_execution and (self.running_execution.state != "running" or self.status == "completed"):
            raise ValueError("Invalid running execution")
        if self.comparable_snapshots == 0 and (self.first_version_count is not None or self.last_version_count is not None):
            raise ValueError("No comparable baseline")
        if self.comparable_snapshots > 0 and (self.first_version_count is None or self.last_version_count is None):
            raise ValueError("Missing comparable baseline")
        if self.changes_detected > max(0, self.comparable_snapshots - 1):
            raise ValueError("Invalid changes count")
        if len(set(self.newly_seen_versions)) != len(self.newly_seen_versions):
            raise ValueError("Repeated newly seen version")
        return self


class WatchCall(Frozen):
    id: str | None = None
    server_label: str | None = None
    name: str | None = None
    arguments: str | None = None
    status: str | None = None
    output: str | None = None
    error: JsonValue = None
    outcome: str
    receipt: WatchReceipt | None = None
    summary: WatchSummary | None = None


class WatchOperation(Frozen):
    operation_id: str
    submitted_prompt: str
    operation: Literal["create", "summary"]
    selected_watch_id: UUID | None = None
    server_url: str | None = None
    response_id: str | None = None
    provider_status: str | None = None
    final_text: str | None = None
    mcp_items: list[dict[str, JsonValue]] = Field(default_factory=list)
    calls: list[WatchCall] = Field(default_factory=list)
    outcome: str
    invocation: Literal["observed", "not_observed", "unknown", "not_sent"]
    error_message: str | None = None
    evidence_saved: bool = False
