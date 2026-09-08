from uuid import uuid4

from app.conversation_store import ConversationStore, SessionNotFound
from app.llm_client import ConversationMessage


class SessionBusy(Exception):
    pass


class AgentSession:
    def __init__(
        self, session_id: str, store: ConversationStore, history: tuple[ConversationMessage, ...] = (),
    ) -> None:
        self.session_id = session_id
        self._store = store
        self._history = history
        self._busy = False
        self._closed = False

    @property
    def history(self) -> tuple[ConversationMessage, ...]:
        return self._history

    @property
    def history_turn_count(self) -> int:
        return len(self._history) // 2

    def ensure_available(self) -> None:
        if self._closed:
            raise SessionNotFound
        if self._busy:
            raise SessionBusy

    def begin_turn(self) -> None:
        # No await: check and claim are atomic on the single worker event loop.
        self.ensure_available()
        self._busy = True

    def commit(self, user: ConversationMessage, assistant: ConversationMessage) -> None:
        if self._closed:
            raise SessionNotFound
        snapshot = (*self._history, user, assistant)
        self._store.append_turn(self.session_id, user, assistant)
        self._history = snapshot

    def end_turn(self) -> None:
        self._busy = False

    def close(self) -> None:
        if self._busy:
            raise SessionBusy
        self._closed = True
        self._history = ()


class AgentSessionManager:
    def __init__(self, store: ConversationStore) -> None:
        self._store = store
        self._sessions: dict[str, AgentSession] = {}

    def create(self) -> AgentSession:
        session_id = str(uuid4())
        self._store.create_session(session_id)
        session = AgentSession(session_id, self._store)
        self._sessions[session.session_id] = session
        return session

    def get(self, session_id: str) -> AgentSession:
        if session_id not in self._sessions:
            saved = self._store.load_session(session_id)
            if saved is None:
                raise SessionNotFound
            self._sessions[session_id] = AgentSession(saved.session_id, self._store, saved.history)
        return self._sessions[session_id]

    def delete(self, session_id: str) -> None:
        session = self._sessions.get(session_id)
        if session is not None:
            session.ensure_available()
        self._store.delete_session(session_id)
        if session is not None:
            session.close()
            del self._sessions[session_id]
