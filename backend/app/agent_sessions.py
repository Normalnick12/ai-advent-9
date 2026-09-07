from uuid import uuid4

from app.llm_client import ConversationMessage


class SessionNotFound(Exception):
    pass


class SessionBusy(Exception):
    pass


class AgentSession:
    def __init__(self) -> None:
        self.session_id = str(uuid4())
        self._history: tuple[ConversationMessage, ...] = ()
        self._busy = False
        self._closed = False

    @property
    def history(self) -> tuple[ConversationMessage, ...]:
        return self._history

    @property
    def history_turn_count(self) -> int:
        return len(self._history) // 2

    def begin_turn(self) -> None:
        # No await: check and claim are atomic on the single worker event loop.
        if self._closed:
            raise SessionNotFound
        if self._busy:
            raise SessionBusy
        self._busy = True

    def commit(self, user: ConversationMessage, assistant: ConversationMessage) -> None:
        if self._closed:
            raise SessionNotFound
        self._history = (*self._history, user, assistant)

    def end_turn(self) -> None:
        self._busy = False

    def close(self) -> None:
        if self._busy:
            raise SessionBusy
        self._closed = True
        self._history = ()


class AgentSessionManager:
    def __init__(self) -> None:
        self._sessions: dict[str, AgentSession] = {}

    def create(self) -> AgentSession:
        session = AgentSession()
        self._sessions[session.session_id] = session
        return session

    def get(self, session_id: str) -> AgentSession:
        try:
            return self._sessions[session_id]
        except KeyError:
            raise SessionNotFound from None

    def delete(self, session_id: str) -> None:
        session = self._sessions.get(session_id)
        if session is not None:
            session.close()
            del self._sessions[session_id]
