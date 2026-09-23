"""Public facts and strict inputs. No MCP or model dependencies."""
from datetime import datetime, timezone
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

GROUP_PATTERN = r"^[A-Za-z0-9_][A-Za-z0-9_-]*(?:\.[A-Za-z0-9_][A-Za-z0-9_-]*)*$"
ARTIFACT_PATTERN = r"^[A-Za-z0-9_][A-Za-z0-9_.-]*$"
GroupId = Annotated[str, Field(strict=True, min_length=1, max_length=256, pattern=GROUP_PATTERN,
                               description="Exact Google Maven group, for example androidx.core")]
ArtifactId = Annotated[str, Field(strict=True, min_length=1, max_length=256, pattern=ARTIFACT_PATTERN,
                                  description="Exact artifact, for example core-ktx; not a URL")]
MaxRuns = Annotated[int, Field(strict=True, ge=1, le=100, description="Finite number of runs, including failures")]
Interval = Annotated[int, Field(strict=True, ge=30, le=86400,
                                description="Seconds between checks; normally at least 3600; default 21600")]
LookupStatus = Literal["found", "no_versions", "group_not_found", "artifact_not_found"]


def utc_ms() -> int:
    return int(datetime.now(timezone.utc).timestamp() * 1000)


def timestamp(value: int | None) -> str | None:
    return None if value is None else datetime.fromtimestamp(value / 1000, timezone.utc).isoformat()


class WatchError(Exception):
    """Only a safe, application-owned category crosses the service boundary."""


class CreateInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    group_id: GroupId
    artifact_id: ArtifactId
    max_runs: MaxRuns
    interval_seconds: Interval = 21600


class Receipt(BaseModel):
    watch_id: UUID
    group_id: str
    artifact_id: str
    interval_seconds: int
    max_runs: int
    created_at: str
    next_run_at: str | None
    status: Literal["active", "completed"]
    runs_total: int = 0
    skipped_slots: int = 0


class Execution(BaseModel):
    run_id: UUID
    watch_id: UUID
    scheduled_at: str
    started_at: str
    completed_at: str | None
    checked_at: str | None
    state: Literal["running", "succeeded", "failed"]
    lookup_outcome: LookupStatus | None
    lookup_id: UUID | None
    source_url: str
    version_count: int | None
    error_category: str | None


class Aggregate(BaseModel):
    runs_total: int = 0
    successful: int = 0
    failed: int = 0
    interrupted: int = 0
    comparable_snapshots: int = 0
    first_checked_at: str | None = None
    last_checked_at: str | None = None
    first_version_count: int | None = None
    last_version_count: int | None = None
    changes_detected: int = 0
    newly_seen_versions: list[str] = Field(default_factory=list)
    latest_execution: Execution | None = None
    through_execution_id: UUID | None = None
    generated_at: str
    executions: list[Execution] = Field(default_factory=list)


class Summary(Receipt, Aggregate):
    running_execution: Execution | None = None
