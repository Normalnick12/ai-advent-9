"""Small local Ollama embedding adapter; no provider framework or downloads."""
import json
import math
import re
import httpx

from ollama_client import check_model, local_url, post_json, MAX_METADATA_BYTES

DEFAULT_MODEL = "qwen3-embedding:0.6b"
QUERY_INSTRUCTION = "Retrieve architecture documentation relevant to the question and selected Kotlin class."
RECIPE = {"provider": "ollama", "normalization": "cosine",
          "document_input": "section-text-v1", "query_input": "question-filename-camel-v1"}


def vector_norm(vector, dimension):
    # Adapted from Week 5 first_rag.core; dimension is profile-specific.
    if not isinstance(vector, list) or len(vector) != dimension:
        raise RuntimeError("Некорректная размерность/components embedding.")
    try:
        if any(type(x) not in (int, float) or not math.isfinite(x) for x in vector):
            raise RuntimeError("Некорректные components embedding.")
        norm = math.sqrt(math.fsum(x * x for x in vector))
    except (OverflowError, ValueError):
        raise RuntimeError("Некорректная норма embedding.") from None
    if not math.isfinite(norm) or norm == 0:
        raise RuntimeError("Некорректная норма embedding.")
    return norm


def get_models(client, base):
    # GET equivalent of Day 27's bounded POST transport, intentionally no retries.
    try:
        with client.stream("GET", local_url(base) + "/api/tags") as response:
            if response.status_code != 200 or response.headers.get("content-encoding", "identity") != "identity":
                raise RuntimeError("Ollama: ошибка списка локальных моделей.")
            data = bytearray()
            for part in response.iter_bytes(chunk_size=8192):
                if len(data) + len(part) > MAX_METADATA_BYTES:
                    raise RuntimeError("Ollama metadata превышает лимит.")
                data.extend(part)
        result = json.loads(data)
        if not isinstance(result, dict) or not isinstance(result.get("models"), list):
            raise ValueError
        return result["models"]
    except (httpx.HTTPError, ValueError, RecursionError):
        raise RuntimeError("Не удалось прочитать локальные модели Ollama.") from None


def model_metadata(client, base, model, capability):
    check_model(model)
    shown = post_json(client, base, "/api/show", json.dumps({"model": model}).encode(), MAX_METADATA_BYTES)
    caps = shown.get("capabilities")
    if shown.get("remote_host") or shown.get("remote_model"):
        raise RuntimeError("Удалённая Ollama-модель запрещена.")
    if not isinstance(caps, list) or capability not in caps or not all(isinstance(c, str) for c in caps):
        raise RuntimeError("Ollama не подтвердила capability модели.")
    wanted = model if ":" in model.rsplit("/", 1)[-1] else model + ":latest"
    matches = [m for m in get_models(client, base) if isinstance(m, dict)
               and m.get("name", m.get("model")) == wanted]
    if len(matches) != 1 or not re.fullmatch(r"(?:sha256:)?[0-9a-f]{64}", str(matches[0].get("digest"))):
        raise RuntimeError("Не найден однозначный digest установленной модели.")
    if matches[0].get("remote_host") or matches[0].get("remote_model"):
        raise RuntimeError("Удалённая модель запрещена.")
    return {"model": model, "digest": matches[0]["digest"]}, shown


def embedding_profile(client, base, model):
    identity, shown = model_metadata(client, base, model, "embedding")
    info = shown.get("model_info", {})
    if not isinstance(info, dict):
        raise RuntimeError("Некорректная metadata embedding-модели.")
    dims = {v for k, v in info.items() if k.endswith(".embedding_length") and type(v) is int}
    if len(dims) != 1 or not 1 <= next(iter(dims)) <= 8192:
        raise RuntimeError("Не подтверждена размерность embedding-модели.")
    return {**RECIPE, **identity, "dimension": dims.pop()}


def check_profile(profile):
    if (not isinstance(profile, dict) or set(profile) != set(RECIPE) | {"model", "digest", "dimension"}
            or any(profile.get(k) != v for k, v in RECIPE.items())
            or type(profile.get("dimension")) is not int or not 1 <= profile["dimension"] <= 8192
            or not re.fullmatch(r"(?:sha256:)?[0-9a-f]{64}", str(profile.get("digest")))):
        raise RuntimeError("Несовместимый embedding profile; нужен index.")
    check_model(profile["model"])


def embed(client, base, profile, texts, *, last=True):
    check_profile(profile)
    if not texts or len(texts) > 8:
        raise ValueError("Embedding batch должен содержать 1..8 текстов.")
    body = json.dumps({"model": profile["model"], "input": texts, "truncate": False,
                       "keep_alive": 0 if last else "5m"}, ensure_ascii=False).encode("utf-8")
    if len(body) > 64 * 1024:
        raise ValueError("Embedding request превышает 64 KiB.")
    response = post_json(client, base, "/api/embed", body, 2 * 1024 * 1024)
    vectors = response.get("embeddings")
    if not isinstance(vectors, list) or len(vectors) != len(texts):
        raise RuntimeError("Embedding count mismatch.")
    for vector in vectors:
        vector_norm(vector, profile["dimension"])
    return vectors


def embed_chunks(client, base, profile, chunks):
    result, batch = [], []
    for chunk in chunks:
        text = chunk["section"] + "\n" + chunk["text"]
        trial = batch + [text]
        # Conservative complete JSON size, not a token estimate.
        size = len(json.dumps({"model": profile["model"], "input": trial, "truncate": False,
                               "keep_alive": "5m"}, ensure_ascii=False).encode("utf-8"))
        if batch and (len(trial) > 8 or size > 64 * 1024):
            result.extend(embed(client, base, profile, batch, last=False))
            batch = []
        batch.append(text)
    if batch:
        result.extend(embed(client, base, profile, batch))
    return result


def embed_query(client, base, profile, query):
    current = embedding_profile(client, base, profile["model"])
    if current != profile:
        raise RuntimeError("Embedding model/profile изменился; выполните index.")
    return embed(client, base, profile,
                 ["Instruct: " + QUERY_INSTRUCTION + "\nQuery: " + query])[0]
