import asyncio
import json
import logging
from uuid import uuid4

import pytest

from lookup import LookupResult
from scheduler import Scheduler
from storage import Store
from watch_models import CreateInput, timestamp


@pytest.mark.asyncio
async def test_long_lookup_skips_grid_slots_without_burst_and_logs_correlate(tmp_path, caplog):
    caplog.set_level(logging.INFO)
    clock = [1000000000000]
    start = clock[0]
    store = Store(tmp_path / "w.db", clock=lambda: clock[0])
    receipt = store.create(CreateInput(group_id="a", artifact_id="b", max_runs=3, interval_seconds=3600))
    lookup_id = str(uuid4())
    calls = []
    async def slow(*args):
        calls.append(args)
        clock[0] += 3600000 * 3
        return LookupResult("found", ["1"], lookup_id, clock[0])
    worker = Scheduler(store, clock=lambda: clock[0], lookup_fn=slow)
    clock[0] += 3600000
    await worker.run_due_jobs()
    await worker.run_due_jobs()
    summary = store.summary(receipt.watch_id)
    assert len(calls) == 1 and summary.skipped_slots == 3
    assert summary.next_run_at == timestamp(start + 3600000 * 5)
    events = [json.loads(record.message) for record in caplog.records if record.name.startswith("day18.")]
    begun = next(e for e in events if e["event"] == "execution_started")
    ended = next(e for e in events if e["event"] == "execution_terminal")
    assert begun["run_id"] == ended["run_id"]
    assert begun["watch_id"] == ended["watch_id"] == str(receipt.watch_id)
    assert ended["lookup_id"] == lookup_id


@pytest.mark.asyncio
async def test_two_overlapping_ticks_claim_once(tmp_path):
    clock = [1000000000000]
    store = Store(tmp_path / "w.db", clock=lambda: clock[0])
    receipt = store.create(CreateInput(group_id="a", artifact_id="b", max_runs=1, interval_seconds=3600))
    entered, release = asyncio.Event(), asyncio.Event()
    calls = []
    async def blocked(*args):
        calls.append(args)
        entered.set()
        await release.wait()
        return LookupResult("found", ["1"], str(uuid4()), clock[0])
    worker = Scheduler(store, clock=lambda: clock[0], lookup_fn=blocked)
    clock[0] += 3600000
    first = asyncio.create_task(worker.run_due_jobs())
    await entered.wait()
    await worker.run_due_jobs()
    assert len(calls) == 1
    release.set()
    await first
    assert store.summary(receipt.watch_id).runs_total == 1
