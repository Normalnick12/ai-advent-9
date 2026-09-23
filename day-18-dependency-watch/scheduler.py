"""One supervised asyncio worker. Persistence owns scheduling, not the timer."""
import asyncio
import json
import logging

from lookup import lookup, LookupFailure
from watch_models import utc_ms

logger = logging.getLogger("day18.scheduler")


class Scheduler:
    def __init__(self, store, *, clock=utc_ms, lookup_fn=lookup):
        self.store, self.clock, self.lookup = store, clock, lookup_fn
        self.stop_event = asyncio.Event()

    async def run_due_jobs(self, now=None):
        now = self.clock() if now is None else now
        for watch_id in self.store.due(now):
            run = self.store.claim(watch_id, now)
            if run is None:
                continue
            logger.info(json.dumps({"event": "execution_started", **{k: run[k] for k in
                ("watch_id", "run_id", "scheduled_at", "started_at")}}))
            try:
                result = await self.lookup(run["group_id"], run["artifact_id"])
            except LookupFailure as exc:
                self.store.finish(run["run_id"], failure=exc)
            else:
                self.store.finish(run["run_id"], result=result)

    async def run(self):
        while not self.stop_event.is_set():
            await self.run_due_jobs()
            try:
                await asyncio.wait_for(self.stop_event.wait(), timeout=1)
            except TimeoutError:
                pass
