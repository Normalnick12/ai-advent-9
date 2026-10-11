import json

import httpx
import pytest

from ollama_client import (check_model, generate, local_url, make_client,
                           supports_thinking, usage_metadata)


@pytest.mark.parametrize("url", ["https://127.0.0.1:11434", "http://example.com", "http://192.168.0.1",
    "http://127.0.0.1:0", "http://user@localhost", "http://localhost/path", "http://localhost?x=1",
    "http://localhost#x", "http://localhost:65536", "http://[::1%25lo0]", "http://127.1", " http://localhost"])
def test_remote_or_ambiguous_url(url):
    with pytest.raises(ValueError):
        local_url(url)


@pytest.mark.parametrize("value", [None, "", "test-cloud", "test:cloud", "../../secret", "a\nsecret"])
def test_invalid_model(value):
    with pytest.raises(ValueError):
        check_model(value)


def test_url_and_http_defaults(monkeypatch):
    monkeypatch.setenv("HTTP_PROXY", "http://proxy.invalid:9999")
    assert local_url("http://localhost:11434/") == "http://127.0.0.1:11434"
    assert local_url("http://[::1]:11434") == "http://[::1]:11434"
    with make_client() as client:
        assert client.trust_env is False and client.follow_redirects is False
        assert client.timeout.connect == 5 and client.timeout.read == 180
        assert not client._mounts  # No environment proxy routing.
        assert client._transport._pool._retries == 0


@pytest.mark.parametrize("caps,expected", [(["completion", "thinking"], True), (["completion"], False)])
def test_show_is_metadata_only(caps, expected):
    def handle(request):
        assert request.url.path == "/api/show"
        assert json.loads(request.content) == {"model": "test"}
        return httpx.Response(200, json={"capabilities": caps})
    with make_client(httpx.MockTransport(handle)) as client:
        assert supports_thinking(client, "http://localhost:11434", "test") is expected


@pytest.mark.parametrize("raw", [{}, {"capabilities": "thinking"}, {"capabilities": []},
    {"capabilities": ["completion"], "remote_host": "external"}, {"error": "SECRET"}])
def test_bad_metadata(raw):
    with make_client(httpx.MockTransport(lambda r: httpx.Response(200, json=raw))) as client:
        with pytest.raises(RuntimeError) as e:
            supports_thinking(client, "http://localhost:11434", "test")
        assert "SECRET" not in str(e.value)


@pytest.mark.parametrize("status", [302, 404, 500])
def test_http_failure_no_follow_up(status):
    calls = []
    def handle(request):
        calls.append(request)
        return httpx.Response(status, headers={"location": "https://external.invalid"}, content=b"SECRET")
    with make_client(httpx.MockTransport(handle)) as client:
        with pytest.raises(RuntimeError) as e:
            generate(client, "http://localhost:11434", b"{}")
    assert len(calls) == 1 and "SECRET" not in str(e.value)


@pytest.mark.parametrize("error", [httpx.ConnectError, httpx.ReadTimeout])
def test_network_failure_no_retry(error):
    calls = []
    def handle(request):
        calls.append(request)
        raise error("SECRET", request=request)
    with make_client(httpx.MockTransport(handle)) as client:
        with pytest.raises(RuntimeError) as e:
            generate(client, "http://localhost:11434", b"{}")
    assert len(calls) == 1 and "SECRET" not in str(e.value)


@pytest.mark.parametrize("body", [b"no json", b"[]", b'{"error":"SECRET"}', b"x" * (256*1024+1)],
                         ids=["invalid-json", "array", "api-error", "oversized"])
def test_bad_chat_response(body):
    with make_client(httpx.MockTransport(lambda r: httpx.Response(200, content=body))) as client:
        with pytest.raises(RuntimeError) as e:
            generate(client, "http://localhost:11434", b"{}")
    assert "SECRET" not in str(e.value)


def test_usage_is_unavailable_not_zero():
    result = usage_metadata({"eval_count": 0, "prompt_eval_count": True, "done_reason": "SECRET"})
    assert result["eval_count"] == 0
    assert result["prompt_eval_count"] == result["done_reason"] == "unavailable"
