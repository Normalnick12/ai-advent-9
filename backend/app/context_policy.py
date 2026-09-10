from dataclasses import dataclass
from typing import Protocol, TYPE_CHECKING

from app.llm_client import ConversationMessage

if TYPE_CHECKING:
    from app.compression_models import CompressionPreparation


@dataclass(frozen=True)
class PreparedHistory:
    messages: tuple[ConversationMessage, ...]
    compression: "CompressionPreparation | None" = None


class ContextPolicy(Protocol):
    async def prepare(self, session_id: str,
                      confirmed_history: tuple[ConversationMessage, ...]) -> PreparedHistory: ...


class FullHistoryContextPolicy:
    async def prepare(self, session_id: str,
                      confirmed_history: tuple[ConversationMessage, ...]) -> PreparedHistory:
        return PreparedHistory(confirmed_history)
