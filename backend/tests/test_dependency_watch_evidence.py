import asyncio
import json
from unittest.mock import AsyncMock

import pytest

from app.dependency_watch_models import WatchRequest
from app.dependency_watch_service import DependencyWatchService


@pytest.mark.asyncio
async def test_cancelled_response_leaves_redacted_attempt_no_replay(tmp_path):
    entered, release = asyncio.Event(), asyncio.Event()
    sdk = AsyncMock()
    async def pending(**kwargs):
        entered.set()
        await release.wait()
    sdk.responses.create.side_effect = pending
    token = "synthetic-secret-day18-token-0123456789"
    service = DependencyWatchService(sdk, server_url="https://watch.example.org/mcp", token=token, evidence_dir=tmp_path)
    task = asyncio.create_task(service.run(WatchRequest(operation="create", prompt="P")))
    await entered.wait()
    attempt = next(tmp_path.glob("*.attempt"))
    assert token not in attempt.read_text()
    assert json.loads(attempt.read_text())["invocation"] == "unknown"
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert sdk.responses.create.await_count == 1


@pytest.mark.asyncio
async def test_evidence_unavailable_prevents_create(tmp_path):
    path = tmp_path / "not-directory"
    path.write_text("keep")
    sdk = AsyncMock()
    service = DependencyWatchService(sdk, server_url="https://watch.example.org/mcp",
        token="synthetic-secret-day18-token-0123456789", evidence_dir=path)
    result = await service.run(WatchRequest(operation="create", prompt="P"))
    assert result.invocation == "not_sent" and result.outcome == "evidence_storage_error"
    sdk.responses.create.assert_not_awaited()
