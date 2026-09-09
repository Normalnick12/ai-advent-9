import asyncio
from dataclasses import replace

from app.agent_sessions import AgentSession
from app.llm_client import AgentConfig, ConversationMessage, LlmClient, LlmResult
from app.token_diagnostics import (
    AgentTurnResult, CountFailure, TokenCounter, TokenDiagnostics, PREFLIGHT_TIMEOUT,
)


class SimpleAgent:
    def __init__(self, client: LlmClient, config: AgentConfig = AgentConfig(),
                 counter: TokenCounter | None = None) -> None:
        self._client = client
        self._config = config
        self._counter = counter

    @property
    def config(self):
        return self._config

    async def count_messages(self, messages, *, include_instructions):
        if self._counter is None:
            raise CountFailure("count_unavailable")
        value = await self._counter.count(messages, self.config,
                                          include_instructions=include_instructions)
        if type(value) is not int or value < 0:
            raise CountFailure("count_invalid_response")
        return value

    async def run_turn(self, session: AgentSession, message: str) -> AgentTurnResult:
        session.begin_turn()
        diagnostics = None
        try:
            user = ConversationMessage("user", message)
            history = session.history
            messages = (*history, user)
            if self._counter is not None:
                diagnostics = TokenDiagnostics(
                    history_turn_count_before=session.history_turn_count,
                    saved_history_tokens=0 if not history else None,
                    history_source="empty_history" if not history else "not_measured",
                    config_version=self.config.version,
                    reserved_output_tokens=self.config.max_output_tokens)
                async def measure():
                    nonlocal diagnostics
                    for name, selected, include in (
                        ("current", (user,), False), ("history", history, False),
                        ("full", messages, True),
                    ):
                        if name == "history" and not history:
                            continue
                        diagnostics = replace(diagnostics, count_calls=diagnostics.count_calls+1)
                        value = await self.count_messages(selected, include_instructions=include)
                        key = {"current": "current_message_tokens", "history": "saved_history_tokens",
                               "full": "preflight_input_tokens"}[name]
                        diagnostics = replace(diagnostics, **{key: value, name+"_source": "provider_preflight"})
                try:
                    await asyncio.wait_for(measure(), timeout=PREFLIGHT_TIMEOUT)
                except (CountFailure, TimeoutError) as exc:
                    code = exc.code if isinstance(exc, CountFailure) else "count_timeout"
                    diagnostics = replace(diagnostics, count_error=code)
                    return AgentTurnResult(LlmResult("error", error_code=code,
                        error_message="Подсчёт токенов не завершён. История не изменена."),
                        diagnostics, error_origin="preflight")
                full = diagnostics.preflight_input_tokens
                diagnostics = replace(diagnostics, reserve_warning=full+self.config.max_output_tokens > diagnostics.context_window)
                if full > diagnostics.context_window:
                    return AgentTurnResult(LlmResult("error", error_code="preflight_context_exceeded",
                        error_message="Preflight input превышает окно. Generation не выполнялась."),
                        diagnostics, error_origin="preflight")
            result = await self._client.complete(messages, self.config)
            committed = False
            if result.status == "completed":
                if not result.reply or not result.reply.strip() or result.error_code:
                    result = replace(result, status="error", reply=None, error_code="llm_invalid_response",
                                     error_message="Модель вернула непригодный ответ. Попробуйте ещё раз.")
                else:
                    session.commit(user, ConversationMessage("assistant", result.reply))
                    committed = True
            return AgentTurnResult(result, diagnostics, generation_attempted=True, committed=committed,
                                   error_origin="provider" if result.error_code else None)
        finally:
            session.end_turn()

    async def probe(self, messages: tuple[ConversationMessage, ...],
                    diagnostics: TokenDiagnostics) -> AgentTurnResult:
        # Caller owns the session guard and consumes authorization before this await.
        # This method deliberately receives no session/store and has no commit path.
        result = await self._client.complete(messages, self.config)
        if result.status == "completed":
            result = replace(result, status="error", reply=None,
                error_code="unexpected_provider_acceptance",
                error_message="Provider неожиданно принял запрос. Переполнение не подтверждено; история не изменена.")
        else:
            result = replace(result, reply=None)
        return AgentTurnResult(result, diagnostics, generation_attempted=True,
                               error_origin="provider" if result.error_code else None)
