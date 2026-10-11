import json
import httpx
import pytest

import local_embeddings as emb
from ollama_client import make_client
import retrieval
from test_knowledge import PROFILE, build


@pytest.mark.parametrize("bad", [[0., 0.], [1.], [True, 1.], [float("nan"), 1.], [float("inf"), 1.], [1e308, 1e308], [10**1000, 1]])
def test_invalid_vectors(bad):
    with pytest.raises(RuntimeError):
        emb.vector_norm(bad, 2)


@pytest.mark.parametrize("field,value", [("provider", "openai"), ("normalization", "none"), ("query_input", "old"), ("document_input", "old"), ("dimension", True), ("digest", "bad")])
def test_profile_rejects_incompatible(field, value):
    with pytest.raises(RuntimeError):
        emb.check_profile({**PROFILE, field: value})


def transport(calls, *, dim=2, digest="a" * 64, remote=False, caps=None, embed_response=None):
    def handle(req):
        data = json.loads(req.content) if req.content else {}
        calls.append((req.url.path, data))
        if req.url.path == "/api/show":
            return httpx.Response(200, json={"capabilities": ["embedding"] if caps is None else caps,
                "model_info": {"qwen3.embedding_length": dim}, "remote_host": "evil" if remote else ""})
        if req.url.path == "/api/tags":
            return httpx.Response(200, json={"models": [{"name": "embed:latest", "digest": digest}]})
        assert req.url.path == "/api/embed"
        assert data["truncate"] is False and len(data["input"]) <= 8 and len(req.content) <= 65536
        return httpx.Response(200, json={"embeddings": [[1., 0.]] * len(data["input"])} if embed_response is None else embed_response)
    return httpx.MockTransport(handle)


def test_batches_and_query_profile_no_retry():
    calls = []
    with make_client(transport(calls)) as client:
        assert emb.embedding_profile(client, "http://127.0.0.1:11434", "embed") == PROFILE
        chunks = [{"section": "r", "text": "x" * 1800}] * 17
        assert len(emb.embed_chunks(client, "http://localhost:11434", PROFILE, chunks)) == 17
        emb.embed_query(client, "http://localhost:11434", PROFILE, "вопрос")
    posts = [d for p, d in calls if p == "/api/embed"]
    assert [len(p["input"]) for p in posts] == [8, 8, 1, 1]
    assert [p["keep_alive"] for p in posts] == ["5m", "5m", 0, 0]
    assert posts[-1]["input"][0].endswith("Query: вопрос")


@pytest.mark.parametrize("kwargs", [{"dim": 3}, {"digest": "b" * 64}, {"remote": True}, {"caps": ["completion"]}])
def test_profile_mismatch_precedes_query_embedding(kwargs):
    calls = []
    with make_client(transport(calls, **kwargs)) as client, pytest.raises(RuntimeError):
        emb.embed_query(client, "http://localhost:11434", PROFILE, "PRIVATE")
    assert not any(p == "/api/embed" for p, _ in calls)


@pytest.mark.parametrize("response", [{}, {"embeddings": []}, {"embeddings": [[0, 0]]}, {"embeddings": [[1, 2, 3]]}])
def test_bad_embed_response(response):
    calls = []
    with make_client(transport(calls, embed_response=response)) as client, pytest.raises(RuntimeError):
        emb.embed(client, "http://localhost:11434", PROFILE, ["private"])
    assert len(calls) == 1


@pytest.mark.parametrize("response", [httpx.Response(302, headers={"location": "https://evil.test"}),
    httpx.Response(500, text="PRIVATE"), httpx.Response(200, content=b"x" * (2 * 1024 * 1024 + 1))])
def test_bounded_transport_no_reflection(response):
    calls = []
    def handle(req):
        calls.append(req)
        return response
    with make_client(httpx.MockTransport(handle)) as client, pytest.raises(RuntimeError) as err:
        emb.embed(client, "http://localhost:11434", PROFILE, ["PRIVATE"])
    assert len(calls) == 1 and "PRIVATE" not in str(err.value)


def test_local_url_and_large_batch_reject_before_http():
    with make_client(httpx.MockTransport(lambda r: pytest.fail("HTTP"))) as client:
        with pytest.raises(ValueError):
            emb.embed(client, "http://evil.test", PROFILE, ["x"])
        with pytest.raises(ValueError):
            emb.embed(client, "http://localhost:11434", PROFILE, ["x" * 65536])


def test_fts_and_cosine_ranks_ties(tmp_path):
    (tmp_path / "a.md").write_text("# PaymentGateway\nsession_id Оплата cart", encoding="utf8")
    (tmp_path / "b.md").write_text("# Other\nNOT DROP TABLE unrelated", encoding="utf8")
    index = build(tmp_path)
    for query in ("PaymentGateway", "paymentgateway", "session_id", "оплата"):
        assert retrieval.search(tmp_path, index, query, "text")[0]["source"] == "a.md"
    assert not retrieval.search(tmp_path, index, "Gateway", "text")
    assert not retrieval.search(tmp_path, index, "????", "text")
    assert retrieval.search(tmp_path, index, '" NOT; DROP TABLE --', "text")[0]["source"] == "b.md"
    hits = retrieval.search(tmp_path, index, "anything", "vector", vector=[1., 0.])
    assert [c["source"] for c in hits] == ["a.md", "b.md"]
    assert all(c["score"] == 1. for c in hits)
    assert len(retrieval.search(tmp_path, index, "x", "vector", 1, [1., 0.])) == 1
    for top in (0, 11, True):
        with pytest.raises(ValueError):
            retrieval.search(tmp_path, index, "x", "text", top)


def test_generic_enrichment_and_limits(tmp_path):
    (tmp_path / "rule.md").write_text("# CheckoutCoordinator\nCheckout coordinator owns orchestration")
    index = build(tmp_path)
    question = "Что делает этот класс?"
    query = retrieval.query_text(question, "folder/CheckoutCoordinator.kt")
    assert query == question + "\nCheckoutCoordinator Checkout Coordinator"
    assert not retrieval.search(tmp_path, index, question, "text")
    assert retrieval.search(tmp_path, index, query, "text")
    with pytest.raises(ValueError):
        retrieval.query_text("x" * 2001)
    with pytest.raises(ValueError):
        retrieval.query_text("x", "a" * 4096 + ".kt")
    with pytest.raises(ValueError):
        retrieval.terms(" ".join("word" + str(i) for i in range(65)))


def test_fts_rejects_concurrent_snapshot_replacement(tmp_path):
    (tmp_path / "a.md").write_text("old")
    previous = build(tmp_path)
    (tmp_path / "a.md").write_text("new")
    build(tmp_path)
    with pytest.raises(RuntimeError, match="Index"):
        retrieval.search(tmp_path, previous, "new", "text")
