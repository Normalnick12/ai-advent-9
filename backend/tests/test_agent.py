import asyncio
from unittest.mock import AsyncMock

import pytest

from app.agent import SimpleAgent
from app.agent_sessions import AgentSessionManager, SessionBusy, SessionNotFound
from app.llm_client import LlmResult


@pytest.mark.asyncio
async def test_full_context_isolation_and_reset():
    client = AsyncMock()
    client.complete.return_value = LlmResult("completed", "Ответ")
    agent = SimpleAgent(client)
    manager = AgentSessionManager()
    a, b = manager.create(), manager.create()
    assert a.session_id != b.session_id
    for message in [" Факт ", "Вопрос", "Ещё", "И ещё"]:
        before = a.history
        await agent.run_turn(a, message)
        sent, config = client.complete.call_args.args
        assert sent[:-1] == before
        assert sent[-1].content == message
        assert config == agent.config
    assert [m.content for m in client.complete.call_args.args[0]][:3] == [" Факт ", "Ответ", "Вопрос"]
    assert a.history_turn_count == 4
    await agent.run_turn(b, "Другая session")
    assert len(client.complete.call_args.args[0]) == 1
    manager.delete(a.session_id)
    manager.delete(a.session_id)
    assert a.history == ()
    with pytest.raises(SessionNotFound):
        manager.get(a.session_id)
    with pytest.raises(SessionNotFound):
        await agent.run_turn(a, "Отложенное сообщение")
    c = manager.create()
    assert c.session_id not in {a.session_id, b.session_id}
    assert c.history == ()
    with pytest.raises(SessionNotFound):
        AgentSessionManager().get(b.session_id)


@pytest.mark.asyncio
@pytest.mark.parametrize("result", [
    LlmResult("incomplete", error_code="llm_incomplete"),
    LlmResult("refused", error_code="llm_refused"),
    LlmResult("error", error_code="llm_timeout"),
    LlmResult("completed", " "), LlmResult("completed"),
])
async def test_failure_does_not_commit(result):
    client = AsyncMock()
    client.complete.return_value = LlmResult("completed", "A1")
    agent, session = SimpleAgent(client), AgentSessionManager().create()
    await agent.run_turn(session, "U1")
    history = session.history
    client.complete.return_value = result
    await agent.run_turn(session, "Неуспешный")
    assert session.history == history
    client.complete.return_value = LlmResult("completed", "A2")
    await agent.run_turn(session, "U2")
    assert [m.content for m in client.complete.call_args.args[0]] == ["U1", "A1", "U2"]


@pytest.mark.asyncio
async def test_busy_parallel_sessions_cancel_and_exception():
    started, release = asyncio.Event(), asyncio.Event()

    async def complete(messages, config):
        if messages[-1].content == "A":
            started.set()
            await release.wait()
        return LlmResult("completed", "Ответ")

    client = AsyncMock()
    client.complete.side_effect = complete
    agent, manager = SimpleAgent(client), AgentSessionManager()
    a, b = manager.create(), manager.create()
    task = asyncio.create_task(agent.run_turn(a, "A"))
    await started.wait()
    assert a.history == ()
    with pytest.raises(SessionBusy):
        await agent.run_turn(a, "Дубликат")
    with pytest.raises(SessionBusy):
        manager.delete(a.session_id)
    await agent.run_turn(b, "B")
    assert client.complete.await_count == 2
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert a.history == ()
    client.complete.side_effect = RuntimeError("private")
    with pytest.raises(RuntimeError):
        await agent.run_turn(a, "Ошибка")
    manager.delete(a.session_id)
