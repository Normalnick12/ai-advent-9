"""One shared explanation operation for CLI and optional HTTP adapter."""
import time
import threading

from chat_context import check_history
from explain import check_inputs
from generation_settings import settings
import grounded_explain as grounded
import knowledge as kn
import knowledge_index as ix
from local_embeddings import embed_query, model_metadata
from ollama_client import check_model, generate, local_url, make_client, usage_metadata
from retrieval import query_text, search, terms
from runtime_errors import RuntimeFailure, WorkspaceUnavailable
from workspace import read_source


class CallState:
    """Ownership of one call, including uncertainty after a transport failure."""
    def __init__(self):
        self.lock = threading.Lock()
        self.cancelled = False
        self.submitted = False
        self.terminal = False

    def cancel(self):
        with self.lock:
            self.cancelled = True

    def check(self):
        with self.lock:
            if self.cancelled:
                raise RuntimeFailure("request_timeout", "Операция отменена до следующего этапа.")

    def begin(self):
        with self.lock:
            if self.cancelled:
                raise RuntimeFailure("request_timeout", "Операция отменена до inference.")
            self.submitted = True

    def finish(self):
        with self.lock:
            self.terminal = True

    @property
    def uncertain(self):
        with self.lock:
            return self.submitted and not self.terminal


def retrieve(root, index, query, mode, top_k, base, transport=None, timeout=None):
    vector = None
    if mode == "vector":
        with make_client(transport, timeout=timeout) as client:
            vector = embed_query(client, base, index.metadata["embedding"], query)
    return search(root, index, query, mode, top_k, vector)


def explain_operation(*, workspace, filename, question, model, mode,
                      knowledge=None, base_url="http://127.0.0.1:11434", top_k=4,
                      num_ctx=8192, num_predict=2048, temperature=0, keep_alive=0,
                      history=None, transport=None, timeout=None, expected_digest=None,
                      state=None, metrics=None):
    metrics = metrics if metrics is not None else {}
    state = state or CallState()
    check_model(model)
    base = local_url(base_url)
    check_inputs(question, num_ctx, num_predict)
    if history is not None:
        check_history(history)
    overrides = settings(temperature, keep_alive)
    root = index = None
    state.check()
    if mode == "none":
        if knowledge is not None:
            raise ValueError("retrieval none не принимает --knowledge.")
    else:
        root = kn.local_root(knowledge)
        kn.separate(root, workspace)
        try:
            index = ix.read(root)
            ix.fresh(root, index)
        except (RuntimeError, OSError) as exc:
            raise RuntimeFailure("knowledge_unavailable", str(exc)) from None
    try:
        source = read_source(workspace, filename)
    except OSError as exc:
        raise WorkspaceUnavailable(str(exc)) from None
    previous = history[-1]["user"] if history else None
    query = query_text(question, source.name, previous) if index is not None else None
    if mode == "text":
        terms(query)  # Bound the combined query before downstream work.
    def pack(hits, thinking=True):
        return grounded.pack(source, question, model, mode, hits, num_ctx, num_predict,
                             thinking=thinking, overrides=overrides, history=history)
    pack([])
    state.check()
    phase = time.perf_counter()
    try:
        hits = [] if index is None else retrieve(root, index, query, mode, top_k, base, transport, timeout)
    finally:
        metrics["retrieval_seconds"] = round(time.perf_counter() - phase, 6)
    body, selected = pack(hits)
    metrics.update(retrieval=mode, selected=len(selected), omitted=len(hits) - len(selected),
                   num_ctx=num_ctx, num_predict=num_predict, **overrides, seed=28, ttft_seconds="unavailable")
    state.check()
    with make_client(transport, timeout=timeout) as client:
        identity, shown = model_metadata(client, base, model, "completion")
        if expected_digest is not None and identity["digest"] != expected_digest:
            raise RuntimeFailure("upstream_unavailable", "Digest модели изменился.")
        thinking = "thinking" in shown["capabilities"]
        metrics.update(identity, think=False if thinking else "not_supported")
        if not thinking:
            body, selected = pack(hits, False)
        phase = time.perf_counter()
        state.begin()
        try:
            response = generate(client, base, body)
            if response.get("done") is True:
                state.finish()
        except RuntimeFailure as exc:
            if exc.rejected:
                state.finish()
            raise
        finally:
            metrics["generation_seconds"] = round(time.perf_counter() - phase, 6)
    metrics.update(usage_metadata(response))
    try:
        result = grounded.parse(response, len(source.lines), grounded.status(mode, selected), selected)
    except RuntimeError as exc:
        raise RuntimeFailure("invalid_model_response", str(exc)) from None
    return result, selected, metrics
