import asyncio
import hashlib
import json
import time
from dataclasses import asdict

from app import compression_models as models
from app.compression_models import Branch, CompressionFailure, CompressionPreparation
from app.compression_metrics import context_metrics, measure_count
from app.compression_scenario import scenario_applicable, verify_facts
from app.conversation_store import ConversationStorageError
from app.conversation_summary_store import SummaryStateError
from app.history_summarizer import context_history, measured_generation
from app.llm_client import ConversationMessage


class CompressionComparison:
    """Reads snapshots and prepares candidates. No save/commit path."""
    def __init__(self, load_summary, summarizer, agent, counter):
        self.load_summary, self.summarizer = load_summary, summarizer
        self.agent, self.counter = agent, counter

    async def run(self, session, question, scenario_id, op):
        session.begin_turn()
        started = time.monotonic()
        try:
            async with asyncio.timeout(models.OPERATION_TIMEOUT):
                history = session.history
                op.question = question
                op.durable_summary = self.load_summary(session.session_id, history)
                op.summary_source = "durable"
                snapshot = json.dumps([session.session_id, [asdict(m) for m in history],
                    asdict(self.agent.config), asdict(op.durable_summary) if op.durable_summary else None,
                    question], ensure_ascii=False, sort_keys=True)
                op.snapshot_id = hashlib.sha256(snapshot.encode()).hexdigest()
                if scenario_id and not scenario_applicable(history, question):
                    op.scenario_status = "not_applicable"
                    op.fail("scenario_not_applicable", "Сценарий непригоден: изменены учебные сообщения или ранний факт повторён в raw tail. Начните чистый прогон либо выполните обычное сравнение.")
                    return
                op.scenario_status = "applicable" if scenario_id else "not_requested"
                prep = CompressionPreparation(op.durable_summary, phase=op.summary_phase)
                preparation_error = None
                try:
                    op.compare_summary = await self.summarizer.prepare_candidate(session.session_id, history, prep)
                    op.summary_source = "compare_local" if prep.phase.generation_attempted else "durable"
                except CompressionFailure as exc:
                    preparation_error = exc.code
                user = ConversationMessage("user", question)
                full = (*history, user)
                compressed = (*context_history(history, op.compare_summary), user) if not preparation_error else ()
                op.context = context_metrics(history, op.compare_summary)
                op.full, op.compressed = Branch(), Branch()

                async def branch(name, messages, result):
                    if name == "compressed" and preparation_error:
                        result.status, result.error_code = "error", preparation_error
                        op.context.compressed_error = preparation_error
                        return
                    count = await measure_count(self.counter, self.agent.config, messages, op.context, name)
                    if count is None or count > op.context.context_window:
                        result.status = "error"
                        result.error_code = getattr(op.context, name+"_error") or "preflight_context_exceeded"
                        return
                    outcome = await measured_generation(lambda: self.agent.generate(messages), result.phase)
                    result.status, result.error_code = outcome.status, outcome.error_code
                    result.reply = outcome.reply if outcome.status == "completed" else None
                    if result.reply and scenario_id:
                        result.score, result.facts = verify_facts(result.reply)

                calls = [branch("full", full, op.full), branch("compressed", compressed, op.compressed)]
                if op.compare_summary:
                    calls.append(measure_count(self.counter, self.agent.config, compressed[:1], op.context, "summary", False))
                await asyncio.gather(*calls)
                op.context.calculate()
                op.status = "completed" if op.full.status == op.compressed.status == "completed" else "partial"
        except TimeoutError:
            op.fail("operation_timeout")
        except (SummaryStateError, ConversationStorageError) as exc:
            op.fail(exc.code if isinstance(exc, SummaryStateError) else "storage_error")
        finally:
            if op.context:
                op.context.calculate()
            for result in (op.full, op.compressed):
                if result and result.status == "not_attempted":
                    result.status, result.error_code = "error", "operation_cancelled"
            op.latency_ms = round((time.monotonic()-started)*1000)
            session.end_turn()
