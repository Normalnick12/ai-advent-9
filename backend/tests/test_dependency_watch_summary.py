import copy
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.dependency_watch_models import WatchSummary


def recovered():
    watch_id = str(uuid4())
    one = {"run_id": str(uuid4()), "watch_id": watch_id, "scheduled_at": "2026-09-23T11:00:00Z",
        "started_at": "2026-09-23T11:00:00Z", "completed_at": "2026-09-23T11:00:01Z",
        "checked_at": "2026-09-23T11:00:01Z", "state": "succeeded", "lookup_outcome": "found",
        "lookup_id": str(uuid4()), "source_url": "https://dl.google.com/dl/android/maven2/androidx/core/group-index.xml",
        "version_count": 2, "error_category": None}
    two = {**one, "run_id": str(uuid4()), "scheduled_at": "2026-09-23T12:00:00Z",
        "started_at": "2026-09-23T12:00:00Z", "completed_at": "2026-09-23T13:00:00Z",
        "checked_at": None, "lookup_id": None, "state": "failed", "lookup_outcome": None,
        "version_count": None, "error_category": "interrupted"}
    return {"watch_id": watch_id, "group_id": "androidx.core", "artifact_id": "core-ktx",
        "interval_seconds": 3600, "max_runs": 3, "created_at": "2026-09-23T10:00:00Z",
        "next_run_at": "2026-09-23T13:00:00Z", "status": "active", "runs_total": 2, "skipped_slots": 0,
        "successful": 1, "failed": 1, "interrupted": 1, "comparable_snapshots": 1,
        "first_checked_at": one["checked_at"], "last_checked_at": one["checked_at"],
        "first_version_count": 2, "last_version_count": 2, "changes_detected": 0,
        "newly_seen_versions": [], "latest_execution": two, "through_execution_id": two["run_id"],
        "generated_at": two["completed_at"], "executions": [one, two], "running_execution": None}


def test_recovered_history_accepted_without_fabricating_outcome():
    summary = WatchSummary.model_validate(recovered())
    assert summary.interrupted == summary.failed == 1
    assert summary.latest_execution.checked_at is None
    assert summary.last_version_count == 2


@pytest.mark.parametrize("key,value", [("successful", 2), ("interrupted", 0), ("comparable_snapshots", 0),
    ("through_execution_id", str(uuid4())), ("last_version_count", None), ("changes_detected", 3),
    ("generated_at", "2026-09-23T13:00:00"), ("next_run_at", None)])
def test_rejects_inconsistent_summary(key, value):
    facts = recovered()
    facts[key] = value
    with pytest.raises(ValidationError):
        WatchSummary.model_validate(facts)
