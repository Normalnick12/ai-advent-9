import asyncio
import hashlib
import json
import math
import time
from dataclasses import dataclass, replace
from secrets import token_urlsafe

from app.agent import SimpleAgent
from app.agent_sessions import AgentSession
from app.llm_client import ConversationMessage, LlmResult
from app.openai_agent_payload import generation_payload
from app.token_diagnostics import AgentTurnResult, CountFailure, TokenDiagnostics

UNIT = "0123456789 abcdefghijklmnopqrstuvwxyz\n"
HEADER = "Это тест заполнения контекста. Далее следует повторяемый учебный ASCII-блок.\n"
ENDING = "Ответь кратко: принято"
MAX_BYTES = 2*1024*1024
PREPARE_TIMEOUT = 90
TTL_SECONDS = 600
CAPACITY = 16


def canonical(messages, config):
    return json.dumps(generation_payload(messages, config), ensure_ascii=False,
                      sort_keys=True, separators=(",", ":")).encode("utf-8")


@dataclass(frozen=True)
class PreparationInfo:
    preparation_id: str
    model: str
    config_version: str
    repeats: int
    unit: str
    header: str
    ending: str
    message_chars: int
    message_utf8_bytes: int
    full_payload_bytes: int
    payload_sha256: str
    sample_start: str
    sample_end: str
    created_at: float
    expires_at: float


@dataclass(frozen=True)
class Prepared:
    session_id: str
    history: tuple
    config: object
    messages: tuple
    diagnostics: TokenDiagnostics
    info: PreparationInfo
    expires_monotonic: float


def error_attempt(code, diagnostics=None):
    return AgentTurnResult(
        LlmResult("error", error_code=code, error_message={
            "preparation_unavailable": "Подготовка устарела или уже использована. Подготовьте новый запрос.",
            "preparation_capacity": "Достигнут лимит временных подготовок. Попробуйте позже.",
            "preparation_bounds": "Не удалось получить допустимый размер. Можно начать отдельный новый диалог.",
            "count_timeout": "Подсчёт не завершился вовремя. История не изменена.",
        }.get(code, "Provider counting не завершён. Generation не выполнялась.")),
        diagnostics, error_origin="preflight" if code.startswith("count_") else "application")


class OverflowPreparations:
    def __init__(self, agent: SimpleAgent):
        self.agent = agent
        self._items: dict[str, Prepared] = {}

    def cleanup(self):
        now = time.monotonic()
        self._items = {k: v for k, v in self._items.items() if v.expires_monotonic > now}

    def invalidate(self, session_id):
        self._items = {k: v for k, v in self._items.items() if v.session_id != session_id}

    async def prepare(self, session: AgentSession):
        session.begin_turn()
        diagnostics = TokenDiagnostics(
            history_turn_count_before=session.history_turn_count,
            saved_history_tokens=0 if not session.history else None,
            history_source="empty_history" if not session.history else "not_measured")
        try:
            self.cleanup()
            self.invalidate(session.session_id)
            if len(self._items) >= CAPACITY:
                return error_attempt("preparation_capacity", diagnostics), None
            history, config = session.history, self.agent.config
            async def build():
                nonlocal diagnostics
                repeats, seen = 8192, set()
                for _ in range(4):
                    if repeats in seen or repeats <= 0 or repeats*len(UNIT) > MAX_BYTES:
                        return error_attempt("preparation_bounds", diagnostics), None
                    seen.add(repeats)
                    def candidate():
                        content = HEADER+UNIT*repeats+ENDING
                        messages = (*history, ConversationMessage("user", content))
                        return content, messages, canonical(messages, config)
                    content, messages, encoded = await asyncio.to_thread(candidate)
                    # Never attach a prior candidate's count to a new payload.
                    diagnostics = replace(diagnostics, preflight_input_tokens=None,
                                          full_source="not_measured", reserve_warning=False)
                    if len(encoded) > MAX_BYTES:
                        return error_attempt("preparation_bounds", diagnostics), None
                    diagnostics = replace(diagnostics, count_calls=diagnostics.count_calls+1)
                    full = await self.agent.count_messages(messages, include_instructions=True)
                    diagnostics = replace(diagnostics, preflight_input_tokens=full,
                                          full_source="provider_preflight", reserve_warning=full+1200 > 128000)
                    if 132000 <= full <= 160000:
                        self.cleanup()
                        if len(self._items) >= CAPACITY:
                            return error_attempt("preparation_capacity", diagnostics), None
                        now = time.time()
                        info = PreparationInfo(token_urlsafe(32), config.model, config.version,
                            repeats, UNIT, HEADER, ENDING, len(content), len(content.encode("utf-8")),
                            len(encoded), hashlib.sha256(encoded).hexdigest(),
                            content[:180], content[-180:], now, now+TTL_SECONDS)
                        self._items[info.preparation_id] = Prepared(session.session_id, history, config,
                            messages, diagnostics, info, time.monotonic()+TTL_SECONDS)
                        return AgentTurnResult(LlmResult("completed"), diagnostics), info
                    if full == 0:
                        break
                    repeats = math.ceil(repeats*140000/full)
                return error_attempt("preparation_bounds", diagnostics), None
            try:
                return await asyncio.wait_for(build(), timeout=PREPARE_TIMEOUT)
            except (CountFailure, TimeoutError) as exc:
                code = exc.code if isinstance(exc, CountFailure) else "count_timeout"
                diagnostics = replace(diagnostics, count_error=code)
                return error_attempt(code, diagnostics), None
        finally:
            session.end_turn()

    async def execute(self, session: AgentSession, preparation_id: str):
        session.begin_turn()
        try:
            self.cleanup()
            prepared = self._items.get(preparation_id)
            if prepared is None or prepared.session_id != session.session_id:
                return error_attempt("preparation_unavailable")
            if prepared.history != session.history or prepared.config != self.agent.config:
                self._items.pop(preparation_id, None)
                return error_attempt("preparation_unavailable")
            encoded = await asyncio.to_thread(canonical, prepared.messages, prepared.config)
            if (hashlib.sha256(encoded).hexdigest() != prepared.info.payload_sha256 or
                    prepared.expires_monotonic <= time.monotonic()):
                self._items.pop(preparation_id, None)
                return error_attempt("preparation_unavailable")
            # No await between consuming permission and entering the one generation attempt.
            self._items.pop(preparation_id)
            return await self.agent.probe(prepared.messages, prepared.diagnostics)
        finally:
            session.end_turn()
