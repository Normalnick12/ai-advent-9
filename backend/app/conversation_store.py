from dataclasses import dataclass
from typing import Protocol

from app.llm_client import ConversationMessage


class SessionNotFound(Exception):
    pass


class ConversationStorageError(Exception):
    """Storage could not confirm an operation; contains no conversation data."""


@dataclass(frozen=True)
class StoredConversation:
    session_id: str
    history: tuple[ConversationMessage, ...]


class ConversationStore(Protocol):
    def create_session(self, session_id: str) -> None: ...

    def load_session(self, session_id: str) -> StoredConversation | None: ...

    def append_turn(
        self, session_id: str, user: ConversationMessage, assistant: ConversationMessage,
    ) -> None: ...

    def delete_session(self, session_id: str) -> None: ...
