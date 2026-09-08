import pytest

from app.agent_sessions import AgentSessionManager
from app.main import app
from app.sqlite_conversation_store import SQLiteConversationStore


@pytest.fixture(autouse=True)
def isolated_agent_database(tmp_path, monkeypatch):
    # Every lifespan in every test must avoid the developer's conversation DB.
    path = tmp_path / "api-conversations.sqlite3"
    monkeypatch.setattr(app.state, "agent_database_path", path)
    return path


@pytest.fixture
def store(tmp_path):
    store = SQLiteConversationStore(tmp_path / "conversations.sqlite3")
    yield store
    store.close()


@pytest.fixture
def manager(store):
    return AgentSessionManager(store)
