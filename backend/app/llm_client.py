from dataclasses import dataclass
from typing import Literal, Protocol


@dataclass(frozen=True)
class ConversationMessage:
    role: Literal["user", "assistant"]
    content: str


@dataclass(frozen=True)
class AgentConfig:
    instructions: str = (
        "Ты — помощник учебного приложения. Отвечай по-русски, ясно и кратко. "
        "Учитывай сообщения текущего диалога. Если пользователь спрашивает о личном "
        "факте или условном обозначении, которого нет в текущем диалоге, скажи, что "
        "не знаешь, и не выдумывай его. Не утверждай, что помнишь другие диалоги."
    )
    model: str = "gpt-5.6"
    reasoning_effort: str = "none"
    max_output_tokens: int = 1200


@dataclass(frozen=True)
class LlmResult:
    status: Literal["completed", "incomplete", "refused", "error"]
    reply: str | None = None
    error_code: str | None = None
    error_message: str | None = None
    incomplete_reason: str | None = None


class LlmClient(Protocol):
    async def complete(
        self, messages: tuple[ConversationMessage, ...], config: AgentConfig
    ) -> LlmResult: ...
