"""Bounded S1–S6 driver. Preview is offline; live requires explicit installation approval."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import time
from types import SimpleNamespace
import uuid

from scenarios import HERE, ROOT, CANDIDATES, fingerprint, manifest, scenario, verify_manifest, documents
from experiment import BASELINE, configuration, delta, profile, residence, memory_snapshot, provider_metrics
import grounded_explain as grounded
import compact_contract as compact
import knowledge as kn
import knowledge_index as ix
from ollama_client import make_client, generate, post_json, MAX_RESPONSE_BYTES, local_url
from rag_cli import retrieve
from retrieval import query_text
from explain import safe_text

BASE = "http://127.0.0.1:11434"
LEDGER = ROOT / ".local/day29-attempts.jsonl"
RAG_ROOT = ROOT / ".local/day29-knowledge"
SCENARIOS = tuple("S" + str(n) for n in range(1, 7))
PROMPT_VARIANT = "explain-evidence-v1"
PROMPT_CORRECTION = (
    "В code_observations.text объясняй своими словами поведение и обязанности кода: "
    "что происходит, при каких условиях и с какими последствиями. Не заменяй объяснение "
    "копией Kotlin или перечислением объявлений; имена API и короткие выражения допустимы. "
    "Каждое наблюдение должно раскрывать отдельный существенный аспект вопроса и ссылаться "
    "только на относящиеся к нему строки. Для упомянутых в вопросе API объясняй значимое "
    "поведение, если оно установлено доступными данными, а не просто повторяй вызов; "
    "неизвестное явно отмечай и не выдумывай. "
    "До включения Markdown-правила проверь, относится ли его область действия к вопросу "
    "и выбранному коду. В applications объясняй эту связь своими словами. Наличие документа "
    "и точной цитаты само по себе не подтверждает вывод. Если подходящих правил нет, "
    "оставь documented_rules и applications пустыми и объясни недостаток сведений "
    "в limitations. Отсутствие подтверждения свойства не означает доказанного отсутствия свойства."
)


def prompt_manifest():
    """Identity of the one reviewed correction; the historical manifest stays unchanged."""
    verify_manifest()
    parent = manifest()
    return {"variant": PROMPT_VARIANT, "parent_manifest_sha256": fingerprint(parent),
            "parent_prompt_sha256": parent["prompt_sha256"], "schema_sha256": parent["schema_sha256"],
            "prompt_sha256": fingerprint(grounded.INSTRUCTIONS + "\n\n" + PROMPT_CORRECTION)}


def prompt_identity(variant):
    if variant is None:
        return {}
    if variant != PROMPT_VARIANT:
        raise ValueError("Only the reviewed prompt correction is allowed.")
    identity = prompt_manifest()
    if identity != json.loads((HERE / "prompt-correction-manifest.json").read_text(encoding="utf-8")):
        raise ValueError("Prompt correction changed; no unreviewed revision.")
    return identity


def check_prompt_job(job):
    identity = prompt_identity(job.get("prompt_variant"))
    if identity and (job["model"] != CANDIDATES[1] or job["config"] != BASELINE
                     or job["operation"] != "chat" or job.get("scenario") not in ("S4", "S6")):
        raise ValueError("Prompt correction is limited to baseline Coder S4/S6.")
    return identity


def contract_manifest():
    verify_manifest()
    parent = manifest()
    return {"variant": compact.VARIANT, "parent_manifest_sha256": fingerprint(parent),
            "parent_prompt_sha256": parent["prompt_sha256"], "parent_schema_sha256": parent["schema_sha256"],
            "prompt_sha256": fingerprint(compact.INSTRUCTIONS), "schema_sha256": fingerprint(compact.SCHEMA)}


def contract_identity(variant):
    if variant is None:
        return {}
    if variant != compact.VARIANT:
        raise ValueError("Only compact-evidence-v1 is supported.")
    identity = contract_manifest()
    if identity != json.loads((HERE / "compact-contract-manifest.json").read_text(encoding="utf-8")):
        raise ValueError("Compact contract changed; review before a new experiment.")
    return identity


def check_contract_job(job):
    identity = contract_identity(job.get("contract_variant"))
    if identity and (job.get("prompt_variant") is not None or job["model"] != CANDIDATES[1]
                     or job["config"] != BASELINE or job["operation"] != "chat"
                     or job.get("scenario") not in ("S4", "S6")):
        raise ValueError("Compact contract is limited to baseline Coder S4/S6 without prompt correction.")
    return identity


def packet(sid, model, config, options, thinking, hits=None, *, prompt_variant=None, contract_variant=None):
    contract = check_contract_job({"model": model, "config": config, "operation": "chat",
                                  "scenario": sid, "prompt_variant": prompt_variant,
                                  "contract_variant": contract_variant})
    source, question, frozen = scenario(sid)
    selected_hits = frozen if hits is None else hits
    mode = "none" if sid == "S1" else "vector"
    body, selected = grounded.pack(source, question, model, mode, selected_hits,
        config["num_ctx"], config["num_predict"], thinking=thinking,
        overrides={k: config[k] for k in ("temperature", "keep_alive")})
    if len(selected) != len(selected_hits):
        raise ValueError("Frozen context omitted; cannot compare.")
    payload = json.loads(body)
    payload["options"].update(options)
    if prompt_identity(prompt_variant):
        payload["messages"][0]["content"] += "\n\n" + PROMPT_CORRECTION
    if contract:
        payload["messages"][0]["content"] = compact.INSTRUCTIONS
        payload["format"] = compact.SCHEMA
    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode()
    if len(body) > 24 * 1024:
        raise ValueError("Request exceeds byte budget (not a token fit check).")
    return source, selected, mode, body


def run_worker(job, transport=None):
    started = time.perf_counter()
    config = configuration(job["config"])
    model = job["model"]
    verify_manifest()
    metrics = {"status": "error", "server_cleanup": "no_inference", "embedding_calls": 0,
               "ttft_seconds": "unavailable"}
    rendered = ""
    phase_name = "metadata"
    try:
        contract = check_contract_job(job)
        if contract:
            metrics["experimental_contract"] = contract
        correction = check_prompt_job(job)
        if correction:
            metrics["prompt_correction"] = correction
        with make_client(transport) as client:
            current, options = profile(client, BASE, model, config, job.get("digest"))
            if job.get("profile") and current["profile_sha256"] != job["profile"]:
                raise RuntimeError("Profile changed before operation.")
            metrics["profile"] = current
            if job["operation"] == "metadata":
                metrics.update(status="completed", server_cleanup="no_inference")
                return {"metrics": metrics, "rendered": ""}
            metrics["memory_before"] = memory_snapshot()
            metrics["residence_before"] = residence(client, BASE, model)
            metrics["cache_state"] = {True: "resident_before", False: "not_resident_before"}.get(metrics["residence_before"]["resident"], "unknown")
            if job["operation"] == "load":
                phase_name = "admission"
                # Explicit admission keeps the model resident for the quality suite.
                body = json.dumps({"model": model, "stream": False, "keep_alive": "5m", "options": options}).encode()
                phase = time.perf_counter()
                metrics["server_cleanup"] = "unknown"
                try:
                    response = post_json(client, BASE, "/api/generate", body, MAX_RESPONSE_BYTES)
                finally:
                    metrics["admission_seconds"] = time.perf_counter() - phase
                metrics.update(provider_metrics(response))
                if response.get("done") is True:
                    metrics["server_cleanup"] = "response_completed"
                if response.get("done") is not True or response.get("done_reason") not in ("load", "stop"):
                    raise RuntimeError("Admission did not complete.")
                phase_name = "readiness"
                ready = residence(client, BASE, model)
                metrics["residence_after"] = ready
                if ready.get("digest") != current["digest"] or ready.get("context_length") != config["num_ctx"]:
                    raise RuntimeError("Readiness digest/context not confirmed.")
            else:
                request_started = time.perf_counter()
                hits = None
                if job["operation"] == "rag":
                    phase_name = "retrieval"
                    # Only our isolated synthetic knowledge is accepted. Index using the existing CLI.
                    expected = {name: (HERE / "fixtures/knowledge/compose.md").read_text(encoding="utf-8") if name == "compose.md"
                                else (ROOT / "day-28-local-architecture-rag/fixtures/knowledge/checkout.md").read_text(encoding="utf-8")
                                for name in ("checkout.md", "compose.md")}
                    snapshot = kn.scan(RAG_ROOT, kn.policy())
                    if snapshot.hashes != {k: kn.digest(v) for k, v in expected.items()}:
                        raise RuntimeError("RAG knowledge differs from the reviewed synthetic set.")
                    index = ix.read(RAG_ROOT)
                    ix.fresh(RAG_ROOT, index)
                    metrics["index_sha256"] = fingerprint({"hashes": index.hashes, "embedding": index.metadata["embedding"]})
                    source, question, _ = scenario(job["scenario"])
                    phase = time.perf_counter()
                    metrics["embedding_calls"] = 1  # planned; if interrupted, completion remains unknown
                    metrics["server_cleanup"] = "unknown"
                    try:
                        hits = retrieve(SimpleNamespace(base_url=BASE, top_k=4), RAG_ROOT, index,
                                        query_text(question, source.name), "vector", transport)
                    finally:
                        metrics["retrieval_seconds"] = time.perf_counter() - phase
                    metrics["residence_after_retrieval"] = residence(client, BASE, model)
                    metrics["server_cleanup"] = "response_completed"
                else:
                    metrics["retrieval_seconds"] = 0
                phase_name = "packing"
                source, selected, mode, body = packet(job["scenario"], model, config, options,
                                                       current["think"] is False, hits,
                                                       prompt_variant=job.get("prompt_variant"),
                                                       contract_variant=job.get("contract_variant"))
                metrics["selected_chunk_ids"] = [c["chunk_id"] for c in selected]
                metrics["input_sha256"] = fingerprint(json.loads(body)["messages"])
                phase_name = "generation"
                phase = time.perf_counter()
                metrics["server_cleanup"] = "unknown"
                try:
                    response = generate(client, BASE, body)
                finally:
                    metrics["generation_seconds"] = time.perf_counter() - phase
                metrics.update(provider_metrics(response))
                if response.get("done") is True:
                    metrics["server_cleanup"] = "response_completed"
                content = response.get("message", {}).get("content")
                if isinstance(content, str):
                    rendered = "Raw synthetic answer (technical/semantic review pending):\n" + safe_text(content)
                phase_name = "validation"
                output_contract = compact if contract else grounded
                result = output_contract.parse(response, len(source.lines), grounded.status(mode, selected), selected)
                metrics["user_request_seconds"] = time.perf_counter() - request_started
                rendered = output_contract.render(result, selected)
                metrics["residence_after"] = residence(client, BASE, model)
            metrics.update(status="completed", server_cleanup="response_completed")
    except Exception:
        # No exception strings, bodies, response content, paths or model reasoning in metrics.
        metrics["status"] = "error"
        metrics["failed_phase"] = phase_name
    finally:
        if "request_started" in locals() and "user_request_seconds" not in metrics:
            metrics["user_request_seconds"] = time.perf_counter() - request_started
        metrics["operation_seconds"] = time.perf_counter() - started
        if "memory_before" in metrics:
            metrics["memory_after"] = memory_snapshot()
    return {"metrics": metrics, "rendered": rendered}


def bounded(command, job, seconds, *, spawn=subprocess.Popen):
    """Only owns the direct Python child. Never kills the Ollama runner or other processes."""
    child = spawn(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                  text=True, encoding="utf-8")
    try:
        out, _ = child.communicate(json.dumps(job), timeout=seconds)
    except (subprocess.TimeoutExpired, KeyboardInterrupt) as error:
        child.kill()
        child.communicate()  # Reap the owned client; this does NOT establish server completion.
        return {"metrics": {"status": "deadline" if isinstance(error, subprocess.TimeoutExpired) else "cancelled",
                            "client_reaped": child.poll() is not None, "server_cleanup": "unknown"}, "rendered": ""}
    if child.returncode != 0:
        return {"metrics": {"status": "worker_error", "server_cleanup": "unknown"}, "rendered": ""}
    try:
        return json.loads(out)
    except ValueError:
        return {"metrics": {"status": "worker_error", "server_cleanup": "unknown"}, "rendered": ""}


# Explicitly allowlisted fields. The worker cannot persist rendered response/content/reasoning.
FIELDS = {"status", "failed_phase", "server_cleanup", "client_reaped", "profile", "embedding_calls", "ttft_seconds",
          "memory_before", "memory_after", "residence_before", "residence_after", "residence_after_retrieval",
          "cache_state", "admission_seconds", "operation_seconds", "user_request_seconds", "retrieval_seconds", "generation_seconds",
          "total_duration_seconds", "load_duration_seconds", "prompt_eval_duration_seconds", "eval_duration_seconds",
          "prompt_eval_count", "eval_count", "done_reason", "selected_chunk_ids", "input_sha256", "index_sha256",
          "prompt_correction", "experimental_contract"}


def emit(record, path=None):
    line = json.dumps(record, ensure_ascii=True, sort_keys=True)
    print(line, file=sys.stderr, flush=True)
    if path is not None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as stream:
            stream.write(line + "\n")
            stream.flush()


def history(path):
    records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()] if path.exists() else []
    starts = {r["attempt"]: r for r in records if r["event"] == "start"}
    ends = {r["attempt"]: r for r in records if r["event"] == "end"}
    # Interrupted starts and unknown server cleanup block further automatic live work.
    blocked = set(starts) - set(ends) or any(r.get("metrics", {}).get("server_cleanup") == "unknown" for r in ends.values())
    used = sum(r["operation"] != "metadata" for r in starts.values())
    elapsed = sum(r.get("client_wall_seconds", 0) for r in ends.values())
    return records, used, elapsed, bool(blocked)


def execute(job, path=LEDGER, runner=bounded):
    contract = check_contract_job(job)
    correction = check_prompt_job(job)
    records, calls, elapsed, blocked = history(path)
    if blocked or calls >= 32 or elapsed >= 90 * 60:
        raise RuntimeError("Live gate closed: incomplete/unknown cleanup or budget exhausted; operator review required.")
    if contract or any(r.get("experimental_contract") for r in records):
        attempts = [r for r in records if r["event"] in ("start", "end")]
        if any(r.get("experimental_contract") != contract for r in attempts):
            raise RuntimeError("Use a separate compact contract journal; preserve historical records.")
        if job.get("scenario") == "S6" and not any(r["event"] == "end" and r.get("scenario") == "S4"
                and r["metrics"]["status"] == "completed" for r in attempts):
            raise RuntimeError("Compact S4 must complete before S6.")
    if correction:
        attempts = [r for r in records if r["event"] in ("start", "end")]
        if any(r.get("prompt_correction") != correction for r in attempts):
            raise RuntimeError("Use a separate correction journal; preserve baseline records.")
        if job["scenario"] == "S6" and not any(r["event"] == "end" and r.get("scenario") == "S4"
                and r["metrics"]["status"] == "completed" for r in attempts):
            raise RuntimeError("Correction S4 must complete before S6.")
    if job["operation"] != "metadata":
        previous = [r for r in records if r["event"] == "end" and r.get("model") == job["model"]
                    and r.get("config") == job["config"] and r.get("operation") != "metadata"]
        if any(r["metrics"]["status"] != "completed" for r in previous):
            raise RuntimeError("This failed configuration is closed; review before any new experiment.")
        if any(r.get("operation") == job["operation"] and r.get("scenario") == job.get("scenario") for r in previous):
            raise RuntimeError("This attempt already exists; reuse it instead of repeating the suite.")
    limit = min(60 if job["operation"] in ("metadata", "load") else 180, 90 * 60 - elapsed)
    common = {"attempt": uuid.uuid4().hex, "model": job["model"], "operation": job["operation"],
              "scenario": job.get("scenario"), "config": job["config"], "manifest_sha256": fingerprint(manifest())}
    if correction:
        common["prompt_correction"] = correction
    if contract:
        common["experimental_contract"] = contract
    start = time.perf_counter()
    emit({**common, "event": "start", "timestamp": time.time(), "deadline_seconds": limit}, path)
    result = runner([sys.executable, "-B", str(HERE / "driver.py"), "--worker"], job, limit)
    metrics = {**provider_metrics({}), **{k: v for k, v in result["metrics"].items() if k in FIELDS}}
    emit({**common, "event": "end", "timestamp": time.time(), "client_wall_seconds": time.perf_counter() - start,
          "metrics": metrics}, path)
    if result.get("rendered"):
        print(result["rendered"], flush=True)  # Terminal only; never in the metrics file.
    return metrics


def reviewed_baseline(records, model):
    rows = [r for r in records if r["event"] == "end" and r.get("model") == model
            and r.get("operation") == "chat" and r.get("config") == BASELINE
            and not r.get("prompt_correction")
            and not r.get("experimental_contract")
            and r.get("manifest_sha256") == fingerprint(manifest())]
    if (len(rows) != 6 or {r.get("scenario") for r in rows} != set(SCENARIOS)
            or any(r["metrics"]["status"] != "completed" for r in rows)):
        raise ValueError("Six completed baseline scenarios required before candidate review.")
    identities = {(r["metrics"]["profile"]["digest"], r["metrics"]["profile"]["profile_sha256"]) for r in rows}
    if len(identities) != 1:
        raise ValueError("Mixed baseline identities cannot select a candidate.")
    return rows[0]["metrics"]["profile"]


def suite(models, config, *, run=execute):
    summary = {}
    load_failures = 0
    for model in models:
        summary[model] = {sid: "NOT RUN" for sid in SCENARIOS}
        job = {"model": model, "config": config, "operation": "metadata"}
        metadata = run(job)
        if metadata["status"] != "completed":
            if metadata.get("server_cleanup") == "unknown":
                break
            continue
        job.update(digest=metadata["profile"]["digest"], profile=metadata["profile"]["profile_sha256"])
        admission = run({**job, "operation": "load"})
        if admission["status"] != "completed":
            load_failures += 1
            if admission.get("server_cleanup") == "unknown":
                break
            continue
        for sid in SCENARIOS:
            result = run({**job, "operation": "chat", "scenario": sid})
            summary[model][sid] = result["status"]
            if result["status"] != "completed":
                break
        if result.get("server_cleanup") == "unknown":
            break
    for model in models:
        summary.setdefault(model, {sid: "NOT RUN" for sid in SCENARIOS})
    if load_failures == 2:
        emit({"event": "diagnostic_proposal", "reason": "both_admissions_failed",
              "next": "Stop; review bounded Ollama logs/version/driver/memory evidence before any new runtime experiment. No automatic warm-up."})
    return summary


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--stage", choices=("preview", "quality", "rag", "variation"), default="preview")
    p.add_argument("--candidate", choices=CANDIDATES)
    p.add_argument("--factor", choices=("keep_alive", "num_predict", "temperature"))
    p.add_argument("--contract-variant", choices=(compact.VARIANT,),
                   help="Offline preview of the experimental contract; live requires separate review")
    p.add_argument("--approved-live-local-only", action="store_true",
                   help="Operator has approved live and verified local-only server configuration; loopback alone is insufficient")
    p.add_argument("--record", action="store_true", help="Opt in to content-free .local/day29-attempts.jsonl")
    p.add_argument("--semantic-reviewed", action="store_true", help="S1–S6 review accepted this provisional candidate")
    p.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    args = p.parse_args(argv)
    if args.contract_variant and (args.stage != "preview" or args.worker):
        p.error("compact contract CLI is preview-only pending separate live review")
    if args.worker:
        print(json.dumps(run_worker(json.load(sys.stdin)), ensure_ascii=True))
        return 0
    verify_manifest()
    if args.stage == "preview":
        preview = {"baseline": BASELINE, "manifest": manifest(), "live": "NOT RUN"}
        if args.contract_variant:
            preview.update(experimental_contract=contract_identity(args.contract_variant), schema=compact.SCHEMA)
        print(json.dumps(preview, indent=2))
        return 0
    if not args.approved_live_local_only or not args.record:
        p.error("live requires installation/user approval, local-only verification and --record; nothing downloaded automatically")
    if args.stage == "quality":
        summary = suite((args.candidate,) if args.candidate else CANDIDATES, BASELINE)
        emit({"event": "summary", "outcomes": summary}, LEDGER)
    else:
        if not args.candidate or not args.semantic_reviewed:
            p.error("review all six scenarios and choose a provisional candidate first")
        baseline = reviewed_baseline(history(LEDGER)[0], args.candidate)
        config = dict(BASELINE)
        if args.stage == "variation":
            if not args.factor:
                p.error("variation needs exactly one factor relative to the baseline")
            config = configuration(BASELINE, args.factor, {"keep_alive": 0, "num_predict": 1024, "temperature": .2}[args.factor])
            emit({"event": "variation", "parent_profile_sha256": baseline["profile_sha256"], **delta(BASELINE, config)}, LEDGER)
        metadata = execute({"model": args.candidate, "config": config, "operation": "metadata", "digest": baseline["digest"]})
        if metadata["status"] != "completed":
            return 1
        unchanged = ("template_sha256", "parameters_sha256", "runtime", "quantization", "think")
        if any(metadata["profile"][k] != baseline[k] for k in unchanged):
            raise ValueError("Candidate metadata changed since baseline review.")
        for sid in ("S2", "S6"):
            result = execute({"model": args.candidate, "config": config, "operation": "rag" if args.stage == "rag" else "chat",
                              "scenario": sid, "digest": metadata["profile"]["digest"], "profile": metadata["profile"]["profile_sha256"]})
            if result["status"] != "completed":
                return 1
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, RuntimeError, OSError):
        print("Experiment stopped; inspect content-free records. No automatic retry or server restart.", file=sys.stderr)
        raise SystemExit(1)
