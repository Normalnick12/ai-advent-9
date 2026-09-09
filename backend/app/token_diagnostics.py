from dataclasses import dataclass, field
from typing import Protocol
from uuid import uuid4

from app.llm_client import AgentConfig, ConversationMessage, LlmResult

DAY08_CONFIG = AgentConfig(model="gpt-4o-mini", reasoning_effort=None,
                           service_tier="default", truncation="disabled",
                           version="day08-gpt4o-mini-v1")
CONTEXT_WINDOW = 128000
COUNT_TIMEOUT = 15
PREFLIGHT_TIMEOUT = 45


class CountFailure(Exception):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


class TokenCounter(Protocol):
    async def count(self, messages: tuple[ConversationMessage, ...], config: AgentConfig,
                    *, include_instructions: bool) -> int: ...


@dataclass(frozen=True)
class TokenDiagnostics:
    current_message_tokens: int | None = None
    saved_history_tokens: int | None = None
    preflight_input_tokens: int | None = None
    current_source: str = "not_measured"
    history_source: str = "not_measured"
    full_source: str = "not_measured"
    config_version: str = DAY08_CONFIG.version
    history_turn_count_before: int = 0
    context_window: int = CONTEXT_WINDOW
    reserved_output_tokens: int = 1200
    count_calls: int = 0
    count_error: str | None = None
    reserve_warning: bool = False


@dataclass(frozen=True)
class AgentTurnResult:
    outcome: LlmResult
    diagnostics: TokenDiagnostics | None = None
    generation_attempted: bool = False
    committed: bool = False
    error_origin: str | None = None
    attempt_id: str = field(default_factory=lambda: uuid4().hex)

    @property
    def status(self):
        return self.outcome.status

    @property
    def reply(self):
        return self.outcome.reply

    @property
    def error_code(self):
        return self.outcome.error_code

    @property
    def error_message(self):
        return self.outcome.error_message

    @property
    def incomplete_reason(self):
        return self.outcome.incomplete_reason
