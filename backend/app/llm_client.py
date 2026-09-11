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
    reasoning_effort: str | None = "none"
    max_output_tokens: int = 1200
    service_tier: str | None = None
    truncation: str | None = None
    version: str | None = None
    text_format: dict | None = None


@dataclass(frozen=True)
class TokenUsage:
    input_tokens: int | None = None
    cached_input_tokens: int | None = None
    cache_write_tokens: int | None = None
    output_tokens: int | None = None
    reasoning_tokens: int | None = None
    total_tokens: int | None = None
    invalid_fields: tuple[str, ...] = ()


@dataclass(frozen=True)
class LlmResult:
    status: Literal["completed", "incomplete", "refused", "error"]
    reply: str | None = None
    error_code: str | None = None
    error_message: str | None = None
    incomplete_reason: str | None = None
    usage: TokenUsage | None = None
    requested_model: str | None = None
    resolved_model: str | None = None
    requested_service_tier: str | None = None
    actual_service_tier: str | None = None
    provider_status: str | None = None


class LlmClient(Protocol):
    async def complete(
        self, messages: tuple[ConversationMessage, ...], config: AgentConfig
    ) -> LlmResult: ...
