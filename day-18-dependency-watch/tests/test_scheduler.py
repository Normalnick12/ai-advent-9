import asyncio
import json
import sqlite3
from uuid import uuid4

import pytest
from pydantic import ValidationError

from lookup import LookupFailure, LookupResult
from scheduler import Scheduler
from storage import Store
from watch_models import CreateInput, WatchError, timestamp

T0 = 1_790_000_000_000
I = 3_600_000


class Clock:
    now = T0
    def __call__(self):
        return self.now


@pytest.fixture
def setup(tmp_path):
    clock = Clock()
    return Store(tmp_path / "w.sqlite3", clock=clock), clock


def request(**changes):
    return CreateInput(**{"group_id": "androidx.core", "artifact_id": "core-ktx", "max_runs": 3,
                         "interval_seconds": 3600, **changes})


def result(clock, versions=None, status="found"):
    return LookupResult(status, ["1"] if versions is None else versions, str(uuid4()), clock())


def complete(store, clock, watch_id, versions=None, status="found", failure=None):
    run = store.claim(str(watch_id), clock())
    assert run
    store.finish(run["run_id"], result=None if failure else result(clock, versions, status), failure=failure)
    return run


def test_create_commits_new_ids_and_read_has_no_side_effect(setup):
    store, clock = setup
    first, second = store.create(request()), store.create(request())
    assert first.watch_id != second.watch_id
    reopened = Store(store.path, clock=clock)
    empty = reopened.summary(first.watch_id)
    assert empty.runs_total == 0 and empty.first_version_count is None
    assert empty.next_run_at == timestamp(T0 + I)
    assert empty == reopened.summary(first.watch_id)
    with pytest.raises(WatchError, match="watch_not_found"):
        reopened.summary(uuid4())


@pytest.mark.parametrize("change", [{"max_runs": True}, {"max_runs": 0}, {"max_runs": 101},
    {"max_runs": 1.0}, {"max_runs": "3"}, {"interval_seconds": True}, {"interval_seconds": 29},
    {"interval_seconds": 86401}, {"group_id": "../x"}, {"artifact_id": "a/b"}])
def test_strict_validation(change):
    with pytest.raises(ValidationError):
        request(**change)


def test_required_defaults_quotas(setup):
    store, _ = setup
    with pytest.raises(ValidationError):
        CreateInput(group_id="a", artifact_id="b")
    assert CreateInput(group_id="a", artifact_id="b", max_runs=100).interval_seconds == 21600
    with pytest.raises(WatchError):
        store.create(request(interval_seconds=30))
    store.allow_short = True
    with pytest.raises(WatchError):
        store.create(request(interval_seconds=30, max_runs=4))
    store.create(request(interval_seconds=30))
    with pytest.raises(WatchError):
        store.create(request(interval_seconds=30))
    for _ in range(4):
        store.create(request())
    with pytest.raises(WatchError):
        store.create(request())


@pytest.mark.asyncio
async def test_three_runs_failed_consumes_budget_and_no_replay(setup):
    store, clock = setup
    receipt = store.create(request())
    calls = []
    async def lookup(*args):
        calls.append(args)
        if len(calls) == 2:
            raise LookupFailure("upstream_timeout", str(uuid4()), clock())
        return result(clock)
    worker = Scheduler(store, clock=clock, lookup_fn=lookup)
    await worker.run_due_jobs()
    assert not calls
    for n in range(1, 4):
        clock.now = T0 + I * n
        await asyncio.gather(worker.run_due_jobs(), worker.run_due_jobs())
        await worker.run_due_jobs()
        assert len(calls) == n
    summary = store.summary(receipt.watch_id)
    assert (summary.runs_total, summary.successful, summary.failed) == (3, 2, 1)
    assert summary.status == "completed" and summary.next_run_at is None
    clock.now += I * 20
    await worker.run_due_jobs()
    assert len(calls) == 3


def test_coalesce_clock_jumps_and_running_snapshot(setup):
    store, clock = setup
    watch = store.create(request())
    clock.now += I * 10 + 1
    run = store.claim(str(watch.watch_id), clock())
    assert run["scheduled_at"] == T0 + I * 10
    snap = store.summary(watch.watch_id)
    assert snap.runs_total == 0 and snap.running_execution.run_id == uuid_from(run)
    assert snap.skipped_slots == 9 and store.claim(str(watch.watch_id), clock()) is None
    clock.now = T0 - I
    store.finish(run["run_id"], result=result(clock))
    assert store.summary(watch.watch_id).next_run_at == timestamp(T0 + I * 11)
    assert not store.due(clock())


def uuid_from(run):
    from uuid import UUID
    return UUID(run["run_id"])


@pytest.mark.parametrize("max_runs", [2, 3])
def test_reopen_recovery_immediate_summary_before_any_tick(tmp_path, max_runs):
    clock = Clock()
    path = tmp_path / "persistent.sqlite3"
    store = Store(path, clock=clock)
    watch = store.create(request(max_runs=max_runs))
    clock.now += I
    complete(store, clock, watch.watch_id)
    clock.now += I
    running = store.claim(str(watch.watch_id), clock())
    clock.now += I * 10
    reopened = Store(path, clock=clock)
    reopened.recover()
    summary = reopened.summary(watch.watch_id)
    assert (summary.interrupted, summary.runs_total, summary.successful, summary.failed) == (1, 2, 1, 1)
    assert summary.through_execution_id == uuid_from(running)
    assert summary.running_execution is None
    assert summary.latest_execution.lookup_outcome is None
    assert summary.latest_execution.checked_at is None
    assert summary.latest_execution.version_count is None
    assert summary.first_version_count == summary.last_version_count == 1
    assert summary.status == ("active" if max_runs == 3 else "completed")
    assert summary.next_run_at == (timestamp(T0 + I * 3) if max_runs == 3 else None)
    with sqlite3.connect(path) as db:
        persisted = json.loads(db.execute("SELECT aggregate_json FROM executions WHERE run_id=?", (running["run_id"],)).fetchone()[0])
        assert persisted == json.loads(db.execute("SELECT aggregate_json FROM watches").fetchone()[0])
        assert all(summary.model_dump(mode="json")[key] == value for key, value in persisted.items())
    again = Store(path, clock=clock)
    again.recover()
    assert again.summary(watch.watch_id) == summary
    if max_runs == 3:
        next_run = again.claim(str(watch.watch_id), clock())
        assert next_run["scheduled_at"] == T0 + I * 12
        assert next_run["run_id"] != running["run_id"]


@pytest.mark.parametrize("recovery", [False, True])
def test_terminalization_rollback_reopen(setup, recovery):
    store, clock = setup
    watch = store.create(request())
    clock.now += I
    running = store.claim(str(watch.watch_id), clock())
    before = store.summary(watch.watch_id)
    def crash(_):
        raise RuntimeError("injected crash")
    store.failpoint = crash
    with pytest.raises(RuntimeError):
        store.recover() if recovery else store.finish(running["run_id"], result=result(clock))
    reopened = Store(store.path, clock=clock)
    assert reopened.summary(watch.watch_id) == before
    reopened.recover()
    assert reopened.summary(watch.watch_id).interrupted == 1


def test_aggregate_sets_gaps_removal_reappearance(setup):
    store, clock = setup
    watch = store.create(request(max_runs=10))
    cases = [(["1", "2"], "found", None), (["2", "1"], "found", None),
        ([], "group_not_found", None), (None, None, LookupFailure("upstream_timeout")),
        (["2", "3"], "found", None), (["3"], "found", None), (["1", "3"], "found", None),
        ([], "no_versions", None)]
    for versions, status, failure in cases:
        clock.now += I
        complete(store, clock, watch.watch_id, versions, status, failure)
    facts = store.summary(watch.watch_id)
    assert (facts.runs_total, facts.successful, facts.failed, facts.comparable_snapshots) == (8, 7, 1, 6)
    assert facts.changes_detected == 4
    assert facts.newly_seen_versions == ["3"]
    assert (facts.first_version_count, facts.last_version_count) == (2, 0)


def test_unknown_schema_not_erased_and_corrupt_database(tmp_path):
    path = tmp_path / "unknown.sqlite3"
    with sqlite3.connect(path) as db:
        db.execute("PRAGMA user_version=999")
        db.execute("CREATE TABLE precious(value)")
        db.execute("INSERT INTO precious VALUES ('keep')")
    with pytest.raises(WatchError, match="unsupported_schema"):
        Store(path)
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT value FROM precious").fetchone()[0] == "keep"
    bad = tmp_path / "bad.sqlite3"
    bad.write_bytes(b"not a database")
    with pytest.raises(WatchError, match="storage_unavailable"):
        Store(bad)


def test_storage_fail_closed_and_unique_slot(setup):
    store, clock = setup
    watch = store.create(request())
    clock.now += I
    run = store.claim(str(watch.watch_id), clock())
    with store.transaction() as db:
        with pytest.raises(sqlite3.IntegrityError):
            db.execute("INSERT INTO executions (run_id,watch_id,scheduled_at,started_at,state,source_url) VALUES (?,?,?,?,'failed','x')",
                       (str(uuid4()), str(watch.watch_id), run["scheduled_at"], clock()))
    with sqlite3.connect(store.path) as db:
        db.execute("DROP TABLE executions")
    with pytest.raises(WatchError, match="storage_unavailable"):
        store.summary(watch.watch_id)
    assert not store.healthy
    with pytest.raises(WatchError):
        store.create(request())
