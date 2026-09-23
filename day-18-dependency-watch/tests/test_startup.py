import asyncio
from unittest.mock import patch

import pytest

from server import create_app
from storage import Store
from watch_models import CreateInput
from lookup import LookupResult
from uuid import uuid4


@pytest.mark.asyncio
async def test_lifespan_recovers_before_readiness_and_first_tick(tmp_path):
    now = [1000000000000]
    path = tmp_path / "w.db"
    store = Store(path, clock=lambda: now[0])
    receipt = store.create(CreateInput(group_id="a", artifact_id="b", max_runs=2, interval_seconds=3600))
    now[0] += 3600000
    run = store.claim(str(receipt.watch_id), now[0])
    store.finish(run["run_id"], result=LookupResult("found", ["1"], str(uuid4()), now[0]))
    now[0] += 3600000
    store.claim(str(receipt.watch_id), now[0])
    calls = []
    async def no_ticks(self):
        await self.stop_event.wait()
    async def unexpected(*args):
        calls.append(args)
        raise AssertionError("lookup during recovery")
    app = create_app(path=path, token="synthetic-secret-sentinel-0123456789", clock=lambda: now[0], lookup_fn=unexpected)
    with patch("scheduler.Scheduler.run", no_ticks):
        async with app.router.lifespan_context(app):
            summary = app.state.store.summary(receipt.watch_id)
            assert (summary.interrupted, summary.runs_total, summary.failed) == (1, 2, 1)
            assert summary.status == "completed" and summary.next_run_at is None
            assert not calls
