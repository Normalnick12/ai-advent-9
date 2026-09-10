import asyncio
import json
import time

from app.compression_models import (CompressionFailure, CompressionPreparation, Phase,
                                    SUMMARY_CONFIG, SUMMARY_MARKER, VERSION)
from app.context_policy import PreparedHistory
from app.conversation_store import ConversationStorageError
from app.conversation_summary_store import SummaryState, SummaryStateError, validate_summary
from app.token_pricing import EstimatedCost
from app.llm_client import ConversationMessage, LlmResult


async def measured_generation(call, phase: Phase):
    started = time.monotonic()
    phase.generation_attempted, phase.status = True, "running"
    phase.cost = EstimatedCost(reason="usage_unavailable")
    try:
        result = await call()
        phase.finish(result)
        return result
    except asyncio.CancelledError:
        phase.status, phase.error_code = "cancelled", "operation_cancelled"
        raise
    except Exception:
        result = LlmResult("error", error_code="llm_upstream_error")
        phase.finish(result)
        return result
    finally:
        phase.latency_ms = round((time.monotonic()-started)*1000)


def context_history(history, summary):
    if summary is None:
        return history
    return (ConversationMessage("assistant", SUMMARY_MARKER+"\n\n"+summary.summary_text),
            *history[summary.covered_through_position+1:])


class HistorySummarizer:
    def __init__(self, client):
        self._client = client

    async def prepare_candidate(self, session_id, history, preparation):
        previous = preparation.durable_summary
        validate_summary(previous, history, VERSION)
        target = max(0, len(history)-4)-1
        before = previous.covered_through_position if previous else -1
        if target == before:
            preparation.candidate = previous
            return previous
        source = json.dumps({"previous_summary": previous.summary_text if previous else None,
            "new_messages": [{"role": m.role, "content": m.content} for m in history[before+1:target+1]]},
            ensure_ascii=False)
        result = await measured_generation(lambda: self._client.complete(
            (ConversationMessage("user", source),), SUMMARY_CONFIG), preparation.phase)
        if result.status != "completed" or not result.reply or not result.reply.strip() or result.error_code:
            if result.status == "completed":
                preparation.phase.status = "error"
                preparation.phase.error_code = "summary_invalid_response"
            raise CompressionFailure(result.error_code or "summary_invalid_response", preparation)
        preparation.candidate = SummaryState(session_id, result.reply, target, VERSION)
        return preparation.candidate


class RollingSummaryContextPolicy:
    def __init__(self, store, summarizer):
        self.store, self.summarizer = store, summarizer

    async def prepare(self, session_id, confirmed_history):
        preparation = CompressionPreparation(self.store.load(session_id, confirmed_history))
        try:
            summary = await self.summarizer.prepare_candidate(session_id, confirmed_history, preparation)
            if summary != preparation.durable_summary:
                self.store.save(summary, confirmed_history, preparation.durable_summary)
                preparation.durable_summary = summary
        except asyncio.CancelledError as exc:
            # The caller still receives the receipt when its own operation deadline cancels preparation.
            exc.preparation = preparation
            raise
        except (ConversationStorageError, SummaryStateError) as exc:
            raise CompressionFailure(exc.code if isinstance(exc, SummaryStateError) else "summary_storage_error", preparation) from None
        return PreparedHistory(context_history(confirmed_history, summary), preparation)
