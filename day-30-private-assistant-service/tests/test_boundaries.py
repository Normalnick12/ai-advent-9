import asyncio
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import json
import logging
from pathlib import Path
import socket
import threading
import time

import httpx
import pytest
from fastapi.testclient import TestClient

from test_service import config, FakeOllama, auth, body, tcp, tcp_server, TOKENS
from laa_service.app import create_app
from laa_service.config import Config, load_config
from laa_service.service import validate_chat
from chat_context import check_history, history_bytes
from client import ChatClient, service_url
from retrieval import query_text, terms
import grounded_explain as grounded
from workspace import Source


@pytest.mark.parametrize("kind,expected", [("length", 413), ("chunks", 413), ("slow", 504),
    ("encoding", 415), ("media", 415), ("json", 422), ("depth", 422)])
def test_raw_asgi_body_bounds(config, kind, expected):
    fake = FakeOllama()
    app = create_app(config, fake.transport(), body_timeout=.01)
    headers = [(b"authorization", ("Bearer " + TOKENS["a"]).encode()), (b"content-type", b"application/json")]
    chunks = [b"{"]
    if kind == "length":
        headers.append((b"content-length", b"32769"))
    elif kind == "chunks":
        chunks = [b"x" * 16000, b"x" * 16769]
    elif kind == "slow":
        chunks = []
    elif kind == "encoding":
        headers.append((b"content-encoding", b"gzip"))
    elif kind == "media":
        headers[-1] = (b"content-type", b"text/plain")
    elif kind == "depth":
        chunks = [b"[" * 2000 + b"]" * 2000]
    messages = []
    async def run():
        async def receive():
            if chunks:
                chunk = chunks.pop(0)
                return {"type": "http.request", "body": chunk, "more_body": bool(chunks)}
            await asyncio.sleep(1)
            return {"type": "http.disconnect"}
        async def send(msg):
            messages.append(msg)
        async with app.router.lifespan_context(app):
            await app({"type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1",
                       "method": "POST", "path": "/v1/chat", "raw_path": b"/v1/chat", "query_string": b"",
                       "headers": headers, "scheme": "http", "server": ("localhost", 1), "client": ("localhost", 2)}, receive, send)
    asyncio.run(run())
    assert messages[0]["status"] == expected and fake.calls == []


def test_exact_history_bytes_and_combined_query():
    history = [{"user": "Navigation", "assistant": "x"}]
    overhead = len(history_bytes(history)) - 1
    history[0]["assistant"] = "x" * (8192 - overhead)
    assert check_history(history) == history
    history[0]["assistant"] += "x"
    with pytest.raises(ValueError):
        check_history(history)
    q = query_text("А когда?", "Fixture.kt", "Navigation")
    assert q == "А когда?\nNavigation\nFixture"
    with pytest.raises(ValueError):
        query_text("a" * 2000, "x" * 100 + ".kt", "b" * 2000)
    with pytest.raises(ValueError):
        terms(query_text(" ".join("v" + str(i) for i in range(40)), "Fixture.kt",
                         " ".join("w" + str(i) for i in range(30))))


def test_combined_term_limit_before_metadata(config):
    fake = FakeOllama()
    with TestClient(create_app(config, fake.transport())) as client:
        payload = body(" ".join("v" + str(i) for i in range(40)),
                       [{"user": " ".join("w" + str(i) for i in range(30)), "assistant": "ignored"}])
        r = client.post("/v1/chat", headers=auth(), json=payload)
        assert r.status_code == 422 and fake.calls == []


def test_history_in_full_budget_and_legacy_bytes():
    source = Source("A.kt", "class A")
    old, _ = grounded.pack(source, "Why?", "gen", "none", [])
    empty, _ = grounded.pack(source, "Why?", "gen", "none", [], history=[])
    assert old == empty
    # Bare source fits; exact same source with bounded history cannot fit.
    large = Source("A.kt", "x" * (16 * 1024))
    grounded.pack(large, "Why?", "gen", "none", [])
    with pytest.raises(ValueError):
        grounded.pack(large, "Why?", "gen", "none", [], history=[{"user": "Why?", "assistant": "x" * 8000}])


@pytest.mark.parametrize("mutation", ["corrupt", "deleted", "source_large", "source_invalid", "symlink"])
def test_data_changes_rechecked(config, mutation, tmp_path):
    fake = FakeOllama()
    if mutation == "corrupt":
        kn_path = config.knowledge / ".laa" / "index.sqlite3"
        kn_path.write_bytes(b"broken")
    elif mutation == "deleted":
        (config.knowledge / "navigation.md").unlink()
    elif mutation == "source_large":
        (config.workspace / "Fixture.kt").write_bytes(b"x" * 16385)
    elif mutation == "source_invalid":
        (config.workspace / "Fixture.kt").write_bytes(b"\xff")
    else:
        source = config.workspace / "Fixture.kt"
        source.unlink()
        outside = tmp_path / "outside.kt"
        outside.write_text("class Secret", encoding="utf-8")
        try:
            source.symlink_to(outside)
        except OSError:
            pytest.skip("Windows symlink privilege unavailable; shared reader junction regression covers Windows")
    with TestClient(create_app(config, fake.transport())) as client:
        assert client.post("/v1/chat", headers=auth(), json=body()).status_code in {422, 503}
    assert fake.calls == []


def test_disconnect_does_not_reuse_slot(config):
    fake = FakeOllama(gate=True)
    app = create_app(config, fake.transport(), deadline=3)
    with tcp_server(app) as base:
        from urllib.parse import urlsplit
        sock = socket.create_connection(("127.0.0.1", urlsplit(base).port))
        raw = json.dumps(body()).encode()
        sock.sendall((f"POST /v1/chat HTTP/1.1\r\nHost: localhost\r\nAuthorization: Bearer {TOKENS['a']}\r\n"
                      f"Content-Type: application/json\r\nContent-Length: {len(raw)}\r\n\r\n").encode() + raw)
        try:
            assert fake.entered.wait(2)
            sock.shutdown(socket.SHUT_RDWR)
            sock.close()
            end = time.monotonic() + 2
            while not app.state.service.recovery and time.monotonic() < end:
                time.sleep(.01)
            assert app.state.service.recovery and len(app.state.service.jobs) == 1
            assert tcp(base, "/healthz")[0] == 200
            code, value = tcp(base, "/v1/chat", "b", body())
            assert code == 503 and value["error"]["code"] == "recovery_required"
        finally:
            sock.close()
            fake.release.set()


def test_bounded_shutdown_preserves_owned_job(config):
    fake = FakeOllama(gate=True)
    app = create_app(config, fake.transport(), shutdown_timeout=.02)
    service = app.state.service
    async def scenario():
        async def never_disconnect():
            await asyncio.Event().wait()
        task = asyncio.create_task(service.chat(body(), "shutdown-test", never_disconnect))
        assert await asyncio.to_thread(fake.entered.wait, 2)
        started = time.monotonic()
        await service.close()
        assert time.monotonic() - started < .5
        assert len(service.jobs) == 1 and service.recovery and service.stopping
        fake.release.set()
        assert (await task)["mechanical_validation"] == "passed"
        await asyncio.sleep(.01)
        assert not service.jobs
    try:
        asyncio.run(scenario())
    finally:
        fake.release.set()


def test_metadata_probe_timeout_keeps_single_probe(config):
    event = threading.Event()
    started = threading.Event()
    calls = []
    def slow(request):
        calls.append(request.url.path)
        started.set()
        assert event.wait(3)
        return httpx.Response(503)
    app = create_app(config, httpx.MockTransport(slow), ready_timeout=.02)
    with TestClient(app) as client:
        try:
            assert client.get("/readyz", headers=auth()).status_code == 503
            app.state.service.invalidate()
            assert client.get("/readyz", headers=auth()).status_code == 503
            assert len(calls) == 1
            assert client.get("/healthz").status_code == 200
        finally:
            event.set()


def test_internal_errors_unknown_routes_do_not_log_inputs(config, caplog):
    app = create_app(config, FakeOllama().transport())
    def explode(*args):
        raise Exception("PRIVATE_PATH PRIVATE_CODE PRIVATE_TOKEN")
    app.state.service._execute = explode
    with TestClient(app) as client, caplog.at_level(logging.INFO, logger="laa.http"):
        r = client.post("/v1/chat", headers=auth(), json=body("PRIVATE_QUERY"))
        assert r.status_code == 500
        unknown = client.get("/PRIVATE_PATH?token=PRIVATE_TOKEN", headers=auth())
        assert unknown.status_code == 404
        assert client.get("/docs", headers=auth()).status_code == 404
        assert "PRIVATE" not in r.text + unknown.text + caplog.text


@pytest.mark.parametrize("url", ["http://192.168.1.2:8030", "https://user:secret@example.org", "https://host/path", "https://host?token=secret"])
def test_client_rejects_unsafe_transport(url):
    with pytest.raises(ValueError):
        service_url(url)


def test_client_history_reset_and_failed_answer():
    calls = []
    failed = [False]
    def handle(req):
        assert req.headers["Authorization"] == "Bearer test-token"
        calls.append(json.loads(req.content))
        if failed[0]:
            return httpx.Response(500, text="PRIVATE")
        return httpx.Response(200, json={"result": {"knowledge_status": "not_requested", "code_observations": [],
            "documented_rules": [], "applications": [], "assumptions": [], "limitations": ["unknown"]},
            "sources": [], "mechanical_validation": "passed", "semantic_status": "not_evaluated"})
    client = ChatClient("https://device.example", "test-token", "demo", transport=httpx.MockTransport(handle))
    try:
        client.ask("Navigation")
        client.ask("А когда?")
        assert calls[1]["history"][0]["user"] == "Navigation"
        assert client.ask("Ещё?")[1] is True
        assert len(client.history) == 2
        before = list(client.history)
        failed[0] = True
        with pytest.raises(ValueError, match="500"):
            client.ask("no")
        assert client.history == before
        client.reset("other")
        assert client.file_id == "other" and client.history == []
    finally:
        client.close()
    assert client.history == []


def test_config_file_secrets_from_environment(config, tmp_path, monkeypatch):
    path = tmp_path / "config.json"
    value = {"workspace": str(config.workspace), "knowledge": str(config.knowledge), "files": config.files,
             "token_env": {"a": "LAA_TEST_ONLY"}, "digest": config.digest,
             "base_url": config.base_url, "local_only_confirmed": True}
    path.write_text(json.dumps(value), encoding="utf-8")
    monkeypatch.setenv("LAA_TEST_ONLY", TOKENS["a"])
    assert load_config(path).tokens == {"a": TOKENS["a"]}
    assert TOKENS["a"] not in path.read_text(encoding="utf-8")
    monkeypatch.delenv("LAA_TEST_ONLY")
    with pytest.raises(ValueError, match="Invalid local"):
        load_config(path)


def test_allowed_file_disappears(config):
    fake = FakeOllama()
    (config.workspace / "Fixture.kt").unlink()
    with TestClient(create_app(config, fake.transport())) as client:
        response = client.post("/v1/chat", headers=auth(), json=body())
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "file_not_found"
        assert fake.calls == []


def test_launcher_loopback_single_worker_no_startup_inference(config, monkeypatch):
    import server
    import laa_service.config as configuration
    import uvicorn
    import sys
    seen = {}
    monkeypatch.setattr(configuration, "load_config", lambda _: config)
    monkeypatch.setattr(uvicorn, "run", lambda app, **kwargs: seen.update(kwargs))
    monkeypatch.setattr(sys, "argv", ["server.py", "--config", "owner-config.json"])
    for name in ("httpx", "httpcore", "uvicorn.access"):
        monkeypatch.setattr(logging.getLogger(name), "disabled", False)
    assert server.main() == 0
    assert seen["host"] == "127.0.0.1" and seen["port"] == 8030 and seen["workers"] == 1
    assert seen["access_log"] is False and seen["proxy_headers"] is False
    assert seen["limit_concurrency"] == 32 and seen["timeout_graceful_shutdown"] == 5
