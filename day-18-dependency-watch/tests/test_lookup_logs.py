import asyncio
import json
import logging

import httpx
import pytest

from lookup import lookup
from watch_models import timestamp


@pytest.mark.asyncio
async def test_log_matches_completed_lookup_timestamp(caplog):
    caplog.set_level(logging.INFO)
    times = iter([1000, 2000, 3000])
    result = await lookup("a", "b", transport=httpx.MockTransport(lambda _: httpx.Response(404)), clock=lambda: next(times))
    event = json.loads(caplog.records[-1].message)
    assert event["checked_at"] == timestamp(result.checked_at)
    assert event["lookup_id"] == result.lookup_id


@pytest.mark.asyncio
async def test_cancelled_lookup_does_not_fabricate_checked_at(caplog):
    caplog.set_level(logging.INFO)
    entered, wait = asyncio.Event(), asyncio.Event()
    async def handler(request):
        entered.set()
        await wait.wait()
        return httpx.Response(200)
    task = asyncio.create_task(lookup("a", "b", transport=httpx.MockTransport(handler)))
    await entered.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    event = json.loads(caplog.records[-1].message)
    assert event["outcome"] == "interrupted" and event["checked_at"] is None
