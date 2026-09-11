import asyncio
from dataclasses import replace

from app.agent_sessions import AgentSession
from app.context_policy import ContextPolicy, FullHistoryContextPolicy
from app.llm_client import AgentConfig, ConversationMessage, LlmClient, LlmResult
from app.token_diagnostics import (
    AgentTurnResult, CountFailure, TokenCounter, TokenDiagnostics, PREFLIGHT_TIMEOUT,
)


class SimpleAgent:
    def __init__(self, client: LlmClient, config: AgentConfig = AgentConfig(),
                 counter: TokenCounter | None = None,
                 context_policy: ContextPolicy | None = None) -> None:
        self._client = client
        self._config = config
        self._counter = counter
        self._context_policy = context_policy or FullHistoryContextPolicy()

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

    async def run_turn(self, session: AgentSession, message: str, *, operation=None, day10=None) -> AgentTurnResult:
        if day10 is not None:
            return await day10.run(self, session, message)
        session.begin_turn()
        diagnostics = None
        try:
            if operation is not None:
                return await self._run_compression_turn(session, message, operation)
            user = ConversationMessage("user", message)
            history = session.history
            prepared = await self._context_policy.prepare(session.session_id, history)
            messages = (*prepared.messages, user)
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
            result = await self.generate(messages)
            committed = False
            if result.status == "completed":
                session.commit(user, ConversationMessage("assistant", result.reply))
                committed = True
            return AgentTurnResult(result, diagnostics, generation_attempted=True, committed=committed,
                                   error_origin="provider" if result.error_code else None)
        finally:
            session.end_turn()

    async def _run_compression_turn(self, session, message, op):
        # Same session guard and atomic pair primitive; only Day 09 supplies an operation receipt.
        import time
        from app import compression_models as models
        from app.compression_models import CompressionFailure
        from app.compression_metrics import context_metrics, measure_contexts
        from app.conversation_store import ConversationStorageError
        from app.conversation_summary_store import SummaryStateError
        from app.history_summarizer import measured_generation

        started = time.monotonic()
        try:
            async with asyncio.timeout(models.OPERATION_TIMEOUT):
                history = session.history
                prepared = await self._context_policy.prepare(session.session_id, history)
                prep = prepared.compression
                op.durable_summary, op.summary_phase = prep.durable_summary, prep.phase
                op.summary_source = "durable"
                user = ConversationMessage("user", message)
                messages = (*prepared.messages, user)
                op.context = context_metrics(history, prep.durable_summary)
                await measure_contexts(self._counter, self.config, (*history, user), messages, op.context)
                if op.context.full_error or op.context.compressed_error:
                    op.fail(op.context.full_error or op.context.compressed_error)
                    return
                if op.context.compressed_input_tokens > op.context.context_window:
                    op.fail("preflight_context_exceeded")
                    return
                result = await measured_generation(lambda: self.generate(messages), op.response_phase)
                if result.status == "completed":
                    try:
                        session.commit(user, ConversationMessage("assistant", result.reply))
                    except ConversationStorageError:
                        op.fail("pair_storage_error")
                        return
                    op.status, op.committed, op.reply = "completed", True, result.reply
                else:
                    op.status = result.status
                    op.error_code = result.error_code or "llm_invalid_response"
                    op.error_message = result.error_message or "Ответ не завершён. История не изменена."
        except CompressionFailure as exc:
            if exc.preparation:
                op.durable_summary = exc.preparation.durable_summary
                op.summary_phase = exc.preparation.phase
                op.summary_source = "durable"
            op.fail(exc.code)
        except (SummaryStateError, ConversationStorageError) as exc:
            op.fail(exc.code if isinstance(exc, SummaryStateError) else "storage_error")
        except TimeoutError as exc:
            cancelled = exc.__cause__
            prep = getattr(cancelled, "preparation", None)
            if prep:
                op.durable_summary, op.summary_phase = prep.durable_summary, prep.phase
                op.summary_source = "durable"
            op.fail("operation_timeout")
        finally:
            op.latency_ms = round((time.monotonic()-started)*1000)
        return None

    async def generate(self, messages: tuple[ConversationMessage, ...]) -> LlmResult:
        """Generate and validate without a session, storage or commit path."""
        result = await self._client.complete(messages, self.config)
        if result.status == "completed" and (
                not result.reply or not result.reply.strip() or result.error_code):
            result = replace(result, status="error", reply=None, error_code="llm_invalid_response",
                             error_message="Модель вернула непригодный ответ. Попробуйте ещё раз.")
        return result

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
