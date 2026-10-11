"""Local Ollama HTTP only; metadata discovery and at most one inference."""
import ipaddress
import json
import re
from urllib.parse import urlsplit

import httpx
from runtime_errors import RuntimeFailure

MAX_RESPONSE_BYTES = 256 * 1024
MAX_METADATA_BYTES = 2 * 1024 * 1024


def local_url(value):
    try:
        if not value or any(c.isspace() or ord(c) < 32 for c in value):
            raise ValueError
        url = urlsplit(value)
        host = url.hostname
        if (url.scheme != "http" or not host or url.username is not None
                or url.password is not None or "?" in value or "#" in value
                or url.path not in {"", "/"} or "%" in host or "\\" in value):
            raise ValueError
        host = "127.0.0.1" if host == "localhost" else host
        ip = ipaddress.ip_address(host)
        port = url.port if url.port is not None else 80
        if not ip.is_loopback or not 1 <= port <= 65535:
            raise ValueError
        return f"http://{'[' + host + ']' if ip.version == 6 else host}:{port}"
    except ValueError:
        raise ValueError("URL должен быть HTTP loopback без credentials, path и query.") from None


def check_model(model):
    if (not isinstance(model, str) or len(model) > 256
            or not re.fullmatch(r"[\w-][\w.-]*(?:/[\w-][\w.-]*)*(?::[\w.-]+)?", model, re.ASCII)
            or model.lower().endswith(("-cloud", ":cloud"))):
        raise ValueError("Укажите имя установленной локальной модели (--model или LAA_MODEL).")


def make_client(transport=None, *, timeout=None):
    return httpx.Client(
        trust_env=False, follow_redirects=False,
        timeout=timeout if timeout is not None else httpx.Timeout(180, connect=5),
        transport=transport if transport is not None else httpx.HTTPTransport(retries=0, trust_env=False),
        headers={"Accept-Encoding": "identity"},
    )


def post_json(client, base_url, endpoint, body, limit):
    # Revalidate here as well: callers cannot bypass the loopback boundary.
    target = local_url(base_url) + endpoint
    try:
        with client.stream("POST", target, content=body, headers={"Content-Type": "application/json"}) as r:
            if not 200 <= r.status_code < 300:
                if r.status_code == 404:
                    raise RuntimeFailure("upstream_unavailable", "Ollama: модель или endpoint не найдены (HTTP 404).", rejected=True)
                raise RuntimeFailure("upstream_overloaded" if r.status_code == 503 else "upstream_unavailable",
                                     f"Ollama вернула HTTP {r.status_code}; повтор не выполняется.",
                                     rejected=r.status_code == 503)
            if r.headers.get("content-encoding", "identity") != "identity":
                raise RuntimeFailure("invalid_model_response", "Неподдерживаемое кодирование ответа Ollama.")
            data = bytearray()
            for chunk in r.iter_bytes(chunk_size=8192):
                if len(data) + len(chunk) > limit:
                    raise RuntimeFailure("invalid_model_response", "Ответ Ollama превышает допустимый размер.")
                data.extend(chunk)
    except httpx.ConnectTimeout:
        raise RuntimeFailure("upstream_unavailable", "Ollama: истекло время ожидания; повтор не выполняется.", rejected=True) from None
    except httpx.TimeoutException:
        raise RuntimeFailure("request_timeout", "Ollama: истекло время ожидания; повтор не выполняется.") from None
    except httpx.ConnectError:
        raise RuntimeFailure("upstream_unavailable", "Не удалось получить ответ локальной Ollama.", rejected=True) from None
    except httpx.HTTPError:
        raise RuntimeFailure("upstream_unavailable", "Не удалось получить ответ локальной Ollama.") from None
    try:
        result = json.loads(data)
    except (ValueError, RecursionError):
        raise RuntimeFailure("invalid_model_response", "Ollama вернула некорректный JSON.") from None
    if not isinstance(result, dict) or "error" in result:
        raise RuntimeFailure("invalid_model_response", "Ollama сообщила ошибку или вернула непригодный ответ.")
    return result


def supports_thinking(client, base_url, model):
    check_model(model)
    response = post_json(client, base_url, "/api/show", json.dumps({"model": model}).encode(), MAX_METADATA_BYTES)
    caps = response.get("capabilities")
    if response.get("remote_host") or response.get("remote_model"):
        raise RuntimeError("Удалённая Ollama-модель запрещена.")
    if not isinstance(caps, list) or not all(isinstance(c, str) for c in caps) or "completion" not in caps:
        raise RuntimeError("Ollama не подтвердила capabilities текстовой модели.")
    return "thinking" in caps


def generate(client, base_url, body):
    return post_json(client, base_url, "/api/chat", body, MAX_RESPONSE_BYTES)


def usage_metadata(response):
    result = {}
    for field in ("prompt_eval_count", "eval_count", "total_duration", "load_duration", "prompt_eval_duration", "eval_duration"):
        value = response.get(field)
        result[field] = value if type(value) is int and value >= 0 else "unavailable"
    reason = response.get("done_reason")
    result["done_reason"] = reason if reason in {"stop", "length"} else "unavailable"
    return result
