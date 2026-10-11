"""Two owned calls, no task queue; workers use the shared synchronous runtime."""
import asyncio
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
import logging
import math
import time

import httpx
from assistant_runtime import CallState, explain_operation
from chat_context import check_history
from explain import check_inputs
import knowledge_index as ix
from local_embeddings import model_metadata
from ollama_client import make_client
from runtime_errors import RuntimeFailure, WorkspaceUnavailable
from workspace import read_source
from .config import ID, MODEL

LOG = logging.getLogger("laa.http")


class ApiError(Exception):
    def __init__(self, status, code, retry=None):
        self.status, self.code, self.retry = status, code, retry


def validate_chat(value):
    try:
        if not isinstance(value, dict) or set(value) - {"file_id", "question", "history"}:
            raise ValueError
        if not isinstance(value.get("file_id"), str) or not ID.fullmatch(value["file_id"]):
            raise ValueError
        check_inputs(value.get("question"), 8192, 2048)
        value["question"].encode("utf-8")
        check_history(value.get("history", []))
    except (ValueError, TypeError, UnicodeError):
        raise ApiError(422, "invalid_request") from None
    return value


class Bucket:
    def __init__(self, capacity, per_minute, clock):
        self.capacity, self.rate, self.clock = capacity, per_minute / 60, clock
        self.tokens, self.updated = capacity, clock()

    def take(self):
        now = self.clock()
        self.tokens = min(self.capacity, self.tokens + max(0, now - self.updated) * self.rate)
        self.updated = now
        if self.tokens < 1:
            raise ApiError(429, "rate_limited", max(1, math.ceil((1 - self.tokens) / self.rate)))
        self.tokens -= 1


@dataclass
class Job:
    state: CallState
    future: asyncio.Future | None = None


class Service:
    def __init__(self, config, transport=None, *, clock=time.monotonic, deadline=120, ready_timeout=5, shutdown_timeout=5):
        self.config, self.transport = config, transport
        self.clock, self.deadline = clock, deadline
        self.ready_timeout, self.shutdown_timeout = ready_timeout, shutdown_timeout
        self.pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="laa-chat")
        self.probe_pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="laa-ready")
        self.jobs = {}
        self.max_active = 0
        self.stopping = False
        self.ready_value, self.ready_at, self.probe = False, float("-inf"), None
        self.buckets = {(label, kind): Bucket(capacity, rate, clock)
                        for label in config.tokens for kind, capacity, rate in (("chat", 2, 6), ("status", 5, 30))}

    @property
    def recovery(self):
        return any(job.state.uncertain and (job.state.cancelled or job.future.done()) for job in self.jobs.values())

    def invalidate(self):
        self.ready_at, self.ready_value = float("-inf"), False

    def status(self):
        return {"ready": self.ready_value and self.clock() - self.ready_at <= 5 and not self.recovery and not self.stopping,
                "recovery_required": self.recovery, "active": len(self.jobs), "limit": 2,
                "max_active": self.max_active, "profile": "coder7b-technical-v1",
                "limits": {"body_bytes": 32768, "history_bytes": 8192, "history_pairs": 2,
                           "question_chars": 2000, "num_ctx": 8192, "num_predict": 2048}}

    def _probe(self):
        try:
            for filename in self.config.files.values():
                read_source(str(self.config.workspace), filename)
            index = ix.read(self.config.knowledge)
            ix.fresh(self.config.knowledge, index)
            with make_client(self.transport, timeout=httpx.Timeout(2, connect=2)) as client:
                identity, _ = model_metadata(client, self.config.base_url, MODEL, "completion")
            return identity["digest"] == self.config.digest
        except Exception:
            return False

    async def readiness(self):
        if self.recovery or self.stopping:
            return False
        if self.clock() - self.ready_at <= 5:
            return self.ready_value
        if self.probe is None or self.probe.done():
            self.probe = asyncio.get_running_loop().run_in_executor(self.probe_pool, self._probe)
        try:
            value = await asyncio.wait_for(asyncio.shield(self.probe), self.ready_timeout)
        except TimeoutError:
            value = False
        self.ready_value, self.ready_at = value, self.clock()
        return value and not self.recovery and not self.stopping

    def _execute(self, body, state):
        result, sources, metrics = explain_operation(
            workspace=str(self.config.workspace), filename=self.config.files[body["file_id"]],
            knowledge=str(self.config.knowledge), question=body["question"], history=body.get("history", []),
            model=MODEL, mode="text", base_url=self.config.base_url, keep_alive="5m",
            expected_digest=self.config.digest, transport=self.transport,
            timeout=httpx.Timeout(120, connect=3), state=state)
        return {"result": result,
                "sources": [{k: c[k] for k in ("chunk_id", "source", "section", "start_line", "end_line")} for c in sources],
                "mechanical_validation": "passed", "semantic_status": "not_evaluated",
                "metrics": {k: metrics[k] for k in ("retrieval_seconds", "generation_seconds", "selected", "omitted",
                           "prompt_eval_count", "eval_count", "done_reason")}}

    def _finished(self, request_id, job):
        # Called in the event loop, even after the HTTP waiter has gone away.
        try:
            exc = job.future.exception()
        except asyncio.CancelledError:
            exc = True
        if exc:
            self.invalidate()
        if not job.state.uncertain:
            self.jobs.pop(request_id, None)
        LOG.info("operation_finished request_id=%s active=%s recovery=%s", request_id, len(self.jobs), self.recovery)

    async def chat(self, body, request_id, receive_disconnect):
        if self.recovery or self.stopping:
            raise ApiError(503, "recovery_required")
        if len(self.jobs) >= 2:
            raise ApiError(503, "capacity_exceeded", 1)
        if body["file_id"] not in self.config.files:
            raise ApiError(404, "file_not_found")
        job = Job(CallState())
        self.jobs[request_id] = job
        self.max_active = max(self.max_active, len(self.jobs))
        job.future = asyncio.get_running_loop().run_in_executor(self.pool, self._execute, body, job.state)
        job.future.add_done_callback(lambda _: self._finished(request_id, job))
        LOG.info("operation_admitted request_id=%s active=%s", request_id, len(self.jobs))
        disconnect = asyncio.create_task(receive_disconnect())
        try:
            done, _ = await asyncio.wait((job.future, disconnect), timeout=self.deadline, return_when=asyncio.FIRST_COMPLETED)
            if job.future not in done:
                job.state.cancel()
                self.invalidate()
                raise ApiError(504, "request_timeout")
            try:
                result = job.future.result()
            except RuntimeFailure as exc:
                code = exc.code
                status = {"invalid_model_response": 502, "request_timeout": 504}.get(code, 503)
                raise ApiError(status, code) from None
            except ValueError:
                raise ApiError(422, "context_budget_exceeded") from None
            except WorkspaceUnavailable:
                raise ApiError(404, "file_not_found") from None
            except OSError:
                raise ApiError(503, "knowledge_unavailable") from None
            except RuntimeError:
                raise ApiError(503, "upstream_unavailable") from None
            return {"request_id": request_id, **result}
        except asyncio.CancelledError:
            job.state.cancel()
            self.invalidate()
            raise
        finally:
            disconnect.cancel()
            await asyncio.gather(disconnect, return_exceptions=True)

    async def close(self):
        self.stopping = True
        pending = [job.future for job in self.jobs.values() if not job.future.done()]
        if pending:
            await asyncio.wait(pending, timeout=self.shutdown_timeout)
        for job in list(self.jobs.values()):
            job.state.cancel()
        LOG.info("service_stopped active=%s recovery=%s", len(self.jobs), self.recovery)
        self.pool.shutdown(wait=False, cancel_futures=True)
        self.probe_pool.shutdown(wait=False, cancel_futures=True)
