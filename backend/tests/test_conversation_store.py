import asyncio
import sqlite3
from unittest.mock import AsyncMock

import pytest

from app.agent import SimpleAgent
from app.agent_sessions import AgentSessionManager, SessionBusy, SessionNotFound
from app.conversation_store import ConversationStorageError
from app.llm_client import ConversationMessage, LlmResult
from app.sqlite_conversation_store import DEFAULT_DATABASE_PATH, SQLiteConversationStore


U1 = ConversationMessage("user", "  U1: сиреневый маяк 🐈\nстрока 2  ")
A1 = ConversationMessage("assistant", "A1: Принято\n✅ ")


@pytest.mark.asyncio
async def test_new_instances_restore_exact_context_and_isolation(tmp_path):
    path = tmp_path / "reopen.sqlite3"
    llm = AsyncMock()
    llm.complete.return_value = LlmResult("completed", A1.content)

    async def original_process():
        store = SQLiteConversationStore(path)
        try:
            manager = AgentSessionManager(store)
            a, b, empty = manager.create(), manager.create(), manager.create()
            agent = SimpleAgent(llm)
            await agent.run_turn(a, U1.content)
            await agent.run_turn(b, "Другой факт")
            # Runtime-only activity must not appear in the reopened store.
            a.begin_turn()
            return a.session_id, b.session_id, empty.session_id
        finally:
            store.close()

    aid, bid, empty_id = await original_process()
    # No original Store/Manager/Session references survive this function scope.
    store = SQLiteConversationStore(path)
    try:
        manager = AgentSessionManager(store)
        assert manager._sessions == {}
        a = manager.get(aid)
        assert set(manager._sessions) == {aid}
        assert a is manager.get(aid)
        assert a.history == (U1, A1)
        assert a.history_turn_count == 1
        agent = SimpleAgent(llm)
        await agent.run_turn(a, "U2")
        messages, config = llm.complete.call_args.args
        assert messages == (U1, A1, ConversationMessage("user", "U2"))
        assert config == agent.config
        assert a.history_turn_count == 2
        await agent.run_turn(manager.get(bid), "B2")
        assert [m.content for m in llm.complete.call_args.args[0]] == ["Другой факт", A1.content, "B2"]
        assert manager.get(empty_id).history == ()
        assert store.load_session("unknown") is None
        with pytest.raises(SessionNotFound):
            manager.get("unknown")
        assert "unknown" not in manager._sessions
    finally:
        store.close()


def test_schema_transaction_rollback_and_delete_reopen(tmp_path):
    path = tmp_path / "transaction.sqlite3"
    store = SQLiteConversationStore(path)
    store.create_session("s1")
    db = store._db()
    assert db.execute("PRAGMA foreign_keys").fetchone() == (1,)
    assert db.execute("PRAGMA journal_mode").fetchone() == ("delete",)
    assert db.execute("PRAGMA synchronous").fetchone() == (2,)
    assert [r[1] for r in db.execute("PRAGMA table_info(sessions)")] == ["session_id"]
    assert [r[1] for r in db.execute("PRAGMA table_info(messages)")] == ["session_id", "position", "role", "content"]
    db.execute("""CREATE TRIGGER fail_assistant BEFORE INSERT ON messages
        WHEN NEW.role = 'assistant' BEGIN SELECT RAISE(ABORT, 'private'); END""")
    with pytest.raises(ConversationStorageError) as error:
        store.append_turn("s1", U1, A1)
    assert str(error.value) == ""
    assert not db.in_transaction
    store.close()
    store = SQLiteConversationStore(path)
    try:
        assert store.load_session("s1").history == ()
        store._db().execute("DROP TRIGGER fail_assistant")
        store.append_turn("s1", U1, A1)
        store.delete_session("s1")
        store.delete_session("s1")
        assert store._db().execute("SELECT COUNT(*) FROM messages").fetchone() == (0,)
    finally:
        store.close()
    store = SQLiteConversationStore(path)
    try:
        assert store.load_session("s1") is None
        with pytest.raises(SessionNotFound):
            store.append_turn("s1", U1, A1)
        assert store.load_session("s1") is None
    finally:
        store.close()


@pytest.mark.parametrize("rows", [
    [(0, "user", "u")],
    [(0, "assistant", "a"), (1, "user", "u")],
    [(0, "system", "x"), (1, "assistant", "a")],
    [(2, "user", "u"), (3, "assistant", "a")],
    [(0, "user", "u"), (3, "assistant", "a")],
])
def test_bad_history_is_never_repaired_or_loaded(store, rows):
    store.create_session("bad")
    db = store._db()
    db.execute("PRAGMA ignore_check_constraints=ON")
    db.executemany("INSERT INTO messages VALUES ('bad', ?, ?, ?)", rows)
    manager = AgentSessionManager(store)
    with pytest.raises(ConversationStorageError):
        manager.get("bad")
    assert manager._sessions == {}
    assert list(db.execute("SELECT position, role, content FROM messages")) == rows


def test_delete_checks_busy_then_persistence_then_closes(store, manager):
    session = manager.create()
    session.commit(U1, A1)
    session.begin_turn()
    with pytest.raises(SessionBusy):
        manager.delete(session.session_id)
    assert store.load_session(session.session_id).history == (U1, A1)
    session.end_turn()
    store._db().execute("""CREATE TRIGGER fail_delete BEFORE DELETE ON sessions
        BEGIN SELECT RAISE(ABORT, 'private'); END""")
    with pytest.raises(ConversationStorageError):
        manager.delete(session.session_id)
    assert manager.get(session.session_id) is session
    assert session.history == (U1, A1)
    session.ensure_available()
    store._db().execute("DROP TRIGGER fail_delete")
    manager.delete(session.session_id)
    assert session.history == ()
    with pytest.raises(SessionNotFound):
        session.begin_turn()
    with pytest.raises(SessionNotFound):
        session.commit(U1, A1)


def test_unloaded_delete_and_storage_failure_never_publish_runtime_objects(store):
    store.create_session("unloaded")
    store.append_turn("unloaded", U1, A1)
    manager = AgentSessionManager(store)
    manager.delete("unloaded")
    assert store.load_session("unloaded") is None
    assert manager._sessions == {}
    store.close()
    with pytest.raises(ConversationStorageError):
        manager.create()
    with pytest.raises(ConversationStorageError):
        manager.get("unloaded")
    assert manager._sessions == {}


class FailCommitConnection:
    def __init__(self, connection):
        self.connection = connection

    def __getattr__(self, name):
        return getattr(self.connection, name)

    def execute(self, sql, *args):
        if sql == "COMMIT":
            raise sqlite3.OperationalError("private commit failure")
        return self.connection.execute(sql, *args)


@pytest.mark.asyncio
async def test_commit_failure_preserves_ram_and_reopened_history(tmp_path):
    path = tmp_path / "commit.sqlite3"
    store = SQLiteConversationStore(path)
    session = AgentSessionManager(store).create()
    session.commit(U1, A1)
    before = session.history
    llm = AsyncMock()
    llm.complete.return_value = LlmResult("completed", "A2")
    store._connection = FailCommitConnection(store._db())
    try:
        with pytest.raises(ConversationStorageError):
            await SimpleAgent(llm).run_turn(session, "U2")
        assert session.history is before
        assert session.history_turn_count == 1
        session.ensure_available()
        assert not store._db().in_transaction
    finally:
        store.close()
    reopened = SQLiteConversationStore(path)
    try:
        assert reopened.load_session(session.session_id).history == before
    finally:
        reopened.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("result", [
    LlmResult("incomplete"), LlmResult("refused"), LlmResult("error"),
    LlmResult("completed", ""), LlmResult("completed", "bad", error_code="bad"), asyncio.CancelledError(),
])
async def test_failed_outcomes_are_absent_after_reopen(tmp_path, result):
    path = tmp_path / "failure.sqlite3"
    store = SQLiteConversationStore(path)
    session = AgentSessionManager(store).create()
    session.commit(U1, A1)
    llm = AsyncMock()
    llm.complete.return_value = result
    try:
        if isinstance(result, asyncio.CancelledError):
            llm.complete.side_effect = result
            with pytest.raises(asyncio.CancelledError):
                await SimpleAgent(llm).run_turn(session, "failed user")
            session.ensure_available()
        else:
            await SimpleAgent(llm).run_turn(session, "failed user")
    finally:
        store.close()
    reopened = SQLiteConversationStore(path)
    try:
        assert reopened.load_session(session.session_id).history == (U1, A1)
    finally:
        reopened.close()


def test_path_does_not_depend_on_cwd_and_connection_closes(tmp_path, monkeypatch):
    expected = DEFAULT_DATABASE_PATH
    monkeypatch.chdir(tmp_path)
    assert DEFAULT_DATABASE_PATH == expected and expected.is_absolute()
    assert expected.parts[-3:] == (".local", "agent", "conversations.sqlite3")
    store = SQLiteConversationStore(tmp_path / "nested" / "test.sqlite3")
    connection = store._db()
    store.close()
    store.close()
    with pytest.raises(sqlite3.ProgrammingError):
        connection.execute("SELECT 1")
    with pytest.raises(ConversationStorageError):
        store.load_session("unknown")


def test_incompatible_schema_is_not_recreated(tmp_path):
    path = tmp_path / "old.sqlite3"
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE sessions (session_id INTEGER PRIMARY KEY)")
        db.execute("INSERT INTO sessions VALUES (1)")
    with pytest.raises(ConversationStorageError):
        SQLiteConversationStore(path)
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT * FROM sessions").fetchall() == [(1,)]
        assert db.execute("SELECT name FROM sqlite_master WHERE name='messages'").fetchall() == []
