import asyncio

from app.compression_models import ContextMetrics
from app.token_diagnostics import CountFailure, PREFLIGHT_TIMEOUT


def context_metrics(history, summary):
    n = summary.covered_through_position+1 if summary else 0
    return ContextMetrics(history_message_count_before=len(history), summarized_message_count=n,
        raw_tail_count=len(history)-n, covered_through_position=n-1 if n else None,
        summary_chars=len(summary.summary_text) if summary else 0,
        summary_standalone_tokens=None if summary else 0,
        summary_source="not_measured" if summary else "absent_summary")


async def measure_count(counter, config, messages, metrics, name, include_instructions=True):
    metrics.count_calls += 1
    try:
        value = await asyncio.wait_for(counter.count(messages, config,
            include_instructions=include_instructions), timeout=PREFLIGHT_TIMEOUT)
        if type(value) is not int or value < 0:
            raise CountFailure("count_invalid_response")
        setattr(metrics, "summary_standalone_tokens" if name == "summary" else name+"_input_tokens", value)
        setattr(metrics, name+"_source", "provider_preflight")
        return value
    except asyncio.CancelledError:
        setattr(metrics, name+"_error", "count_cancelled")
        raise
    except (CountFailure, TimeoutError) as exc:
        code = exc.code if isinstance(exc, CountFailure) else "count_timeout"
        setattr(metrics, name+"_error", code)
    except Exception:
        setattr(metrics, name+"_error", "count_unavailable")
    return None


async def measure_contexts(counter, config, full, compressed, metrics):
    if full == compressed:
        await measure_count(counter, config, full, metrics, "full")
        metrics.compressed_input_tokens = metrics.full_input_tokens
        metrics.compressed_error = metrics.full_error
        if metrics.full_input_tokens is not None:
            metrics.full_source = metrics.compressed_source = "identical_payload"
    else:
        await asyncio.gather(measure_count(counter, config, full, metrics, "full"),
                             measure_count(counter, config, compressed, metrics, "compressed"),
                             measure_count(counter, config, compressed[:1], metrics, "summary", False))
    metrics.calculate()
