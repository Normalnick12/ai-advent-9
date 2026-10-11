"""Ollama 0.40.2 experiment metadata and snapshots, not a benchmark framework."""
import ctypes
import json
import math
import os
import re
import subprocess
import time

from scenarios import CANDIDATES, fingerprint
from generation_settings import settings
from local_embeddings import get_models, model_metadata
from ollama_client import MAX_METADATA_BYTES, local_url

BASELINE = {"num_ctx": 8192, "num_predict": 2048, "temperature": 0, "keep_alive": "5m"}
SAMPLING = {"seed": 28, "top_k": 20, "top_p": .95, "min_p": 0,
            "repeat_last_n": 64, "repeat_penalty": 1, "presence_penalty": 0, "frequency_penalty": 0}
# API defaults at v0.40.2 api/types.go. typical_p is deprecated/accepted but may be inactive.
DEFAULTS = {"num_keep": 4, "typical_p": 1.0, "stop": [], "num_batch": 512,
            "num_gpu": -1, "num_thread": 0, "draft_num_predict": 4, "use_mmap": None, "main_gpu": None}


def configuration(parent=None, factor=None, value=None, *, token_fit=False):
    current = dict(BASELINE if parent is None else parent)
    if set(current) != set(BASELINE):
        raise ValueError("Only four experiment controls are supported.")
    if factor is not None:
        if factor not in BASELINE:
            raise ValueError("Unsupported experiment factor.")
        current[factor] = value
    settings(current["temperature"], current["keep_alive"])
    if type(current["num_predict"]) is not int or current["num_predict"] not in (1024, 2048):
        raise ValueError("num_predict must be 1024 or 2048.")
    if type(current["num_ctx"]) is not int or current["num_ctx"] not in (4096, 8192):
        raise ValueError("num_ctx must be 4096 or 8192.")
    if current["num_ctx"] < 8192 and not token_fit:
        raise ValueError("Token fit requires external tokenizer/template evidence; byte budget is insufficient.")
    return current


def delta(parent, child):
    changed = {k: child[k] for k in child if child[k] != parent.get(k)}
    if set(parent) != set(child) or len(changed) != 1:
        raise ValueError("Exactly one factor must change.")
    return {"parent": fingerprint(parent), "delta": changed}


def get_json(client, base, endpoint):
    if endpoint not in ("/api/version", "/api/ps"):
        raise ValueError("Read-only metadata endpoint required.")
    try:
        with client.stream("GET", local_url(base) + endpoint) as response:
            if response.status_code != 200 or response.headers.get("content-encoding", "identity") != "identity":
                raise ValueError
            data = bytearray()
            for part in response.iter_bytes(chunk_size=8192):
                data.extend(part)
                if len(data) > MAX_METADATA_BYTES:
                    raise ValueError
        result = json.loads(data)
        if not isinstance(result, dict):
            raise ValueError
        return result
    except Exception:
        raise RuntimeError("Metadata unavailable.") from None


def profile(client, base, model, config, expected_digest=None):
    if model not in CANDIDATES:
        raise ValueError("Only the two reviewed Q4 candidates are allowed.")
    # Check installation before show. No pull, auto substitution or historical warm-up.
    installed = [m for m in get_models(client, base) if m.get("name") == model]
    if len(installed) != 1:
        raise RuntimeError("Candidate NOT INSTALLED.")
    version = get_json(client, base, "/api/version").get("version")
    if version != "0.40.2":
        raise RuntimeError("Runtime defaults unknown; review this runtime before live.")
    identity, shown = model_metadata(client, base, model, "completion")
    if expected_digest is not None and identity["digest"] != expected_digest:
        raise RuntimeError("Model digest changed; no silent replacement.")
    if shown.get("details", {}).get("quantization_level") != "Q4_K_M" or not isinstance(shown.get("template"), str):
        raise RuntimeError("Quantization/template NOT READY.")
    options = dict(DEFAULTS)
    provenance = {k: "runtime_default_0.40.2" for k in options}
    inherited = {}
    for line in shown.get("parameters", "").splitlines():
        if not line.strip():
            continue
        key, raw = line.split(None, 1)
        if key not in set(DEFAULTS) | set(SAMPLING) | {"temperature", "num_ctx", "num_predict"}:
            raise RuntimeError("Unknown inherited option; review before live.")
        try:
            value = json.loads(raw)
        except ValueError:
            raise RuntimeError("Unresolved inherited option.") from None
        if key == "stop":
            if not isinstance(value, str):
                raise RuntimeError("Invalid stop metadata.")
            inherited.setdefault(key, []).append(value)
        elif value is not None and (type(value) not in (int, float, bool) or (type(value) is float and not math.isfinite(value))):
            raise RuntimeError("Invalid numeric metadata.")
        else:
            inherited[key] = value
    options.update(inherited)
    provenance.update({k: "model" for k in inherited})
    explicit = {**SAMPLING, **{k: v for k, v in config.items() if k != "keep_alive"}}
    options.update(explicit)
    provenance.update({k: "explicit" for k in explicit})
    # Template + inherited stop are hashed, never written verbatim to content-free records.
    safe_options = {**options, "stop": {"sha256": fingerprint(options["stop"]), "count": len(options["stop"])}}
    record = {**identity, "runtime": version, "quantization": "Q4_K_M", "backend": "unavailable",
              "template_sha256": fingerprint(shown["template"]), "parameters_sha256": fingerprint(shown.get("parameters", "")),
              "options": safe_options, "provenance": provenance, "keep_alive": config["keep_alive"],
              "think": False if "thinking" in shown["capabilities"] else "not_supported",
              "effective_scope": "API resolved; backend activation not observable; typical_p deprecated"}
    record["profile_sha256"] = fingerprint(record)
    # Forward only explicit sampler options. Model/runtime inheritance stays native.
    return record, explicit


def residence(client, base, model):
    try:
        matches = [m for m in get_json(client, base, "/api/ps")["models"] if m.get("name", m.get("model")) == model]
        if not matches:
            return {"resident": False}
        if len(matches) != 1:
            raise ValueError
        m = matches[0]
        digest = m.get("digest")
        return {"resident": True, "digest": digest if re.fullmatch(r"(?:sha256:)?[a-f0-9]{64}", str(digest)) else "unavailable",
                **{k: m[k] if type(m.get(k)) is int and m[k] >= 0 else "unavailable"
                   for k in ("size", "size_vram", "context_length")}}
    except Exception:
        return {"resident": "unavailable"}


def provider_metrics(response):
    result = {"ttft_seconds": "unavailable"}
    for field in ("total_duration", "load_duration", "prompt_eval_duration", "eval_duration"):
        n = response.get(field)
        result[field + "_seconds"] = n / 1e9 if type(n) is int and n >= 0 else "unavailable"
    for field in ("prompt_eval_count", "eval_count"):
        n = response.get(field)
        result[field] = n if type(n) is int and n >= 0 else "unavailable"
    result["done_reason"] = response.get("done_reason") if response.get("done_reason") in ("stop", "load", "length") else "unavailable"
    return result


def memory_snapshot():
    result = {"method": "before_after_snapshot_not_peak", "system_ram_total_bytes": "unavailable",
              "system_ram_available_bytes": "unavailable", "system_gpu_used_mib": "unavailable",
              "runner_rss_bytes": "unavailable", "process_commit_bytes": "unavailable"}
    if os.name == "nt":
        class MemoryStatus(ctypes.Structure):
            _fields_ = [("length", ctypes.c_ulong), ("load", ctypes.c_ulong)] + [(k, ctypes.c_ulonglong) for k in
                ("total", "available", "page_total", "page_available", "virtual_total", "virtual_available", "extended")]
        mem = MemoryStatus()
        mem.length = ctypes.sizeof(mem)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(mem)):
            result.update(system_ram_total_bytes=mem.total, system_ram_available_bytes=mem.available)
    try:
        output = subprocess.run(["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
                                capture_output=True, text=True, timeout=5, check=True)
        values = [int(v.strip()) for v in output.stdout.splitlines()]
        if values and all(v >= 0 for v in values):
            result["system_gpu_used_mib"] = values
    except (OSError, ValueError, subprocess.SubprocessError):
        pass
    result["timestamp"] = time.time()
    return result
