"""One sequential experiment, simple checkpoints; no resume or replay."""
import json
import os
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from uuid import uuid4

from app.agent import SimpleAgent
from app.document_indexing.embedding import EMBEDDING_CONFIG
from app.first_rag.core import CONFIG, messages, search, source_path_hit, vector_norm
from app.openai_agent_payload import generation_payload


def write_json(path, value):
    """Same-directory replacement keeps the last complete checkpoint on failure."""
    path = Path(path)
    temporary = path.with_suffix(".tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(path)


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def phase():
    return {"status": "not_dispatched", "attempted": False, "usage": None}


def review_template(run):
    return {"schema_version": 1, "eval_id": run["eval_id"], "question_hash": run["question_hash"],
            "reviewer": None, "questions": {q["id"]: {
                "status": "pending", "facts": {f["id"]: {
                    "expected_fact_in_retrieved_context": None, "direct_answer_covers_fact": None,
                    "rag_answer_covers_fact": None, "notes": ""} for f in q["expected_facts"]},
                "claims": [], "diagnosis": [], "notes": ""} for q in run["questions"]}}


async def run_experiment(command, questions, *, output_root, index=None, embedder=None,
                         client=None, frozen=None, question_hash=None, progress=print):
    if command not in {"eval", "search", "direct", "rag"}:
        raise ValueError("Unknown experiment command")
    folder = Path(output_root) / str(uuid4())
    folder.mkdir(parents=True, exist_ok=False)
    run = dict(schema_version=1, eval_id=folder.name, command=command,
               created_at=datetime.now(timezone.utc).isoformat(), status="partial",
               index=index.provenance if index else None, config=asdict(CONFIG),
               question_hash=question_hash, frozen_question_set=frozen, questions=questions)
    write_json(folder / "run.json", run)
    write_json(folder / "review.json", review_template(run))
    records = []
    for q in questions:
        record = dict(id=q["id"], question=q["question"],
                      expectations_reference={"question_hash": question_hash, "id": q["id"]},
                      retrieval={**phase(), "hits": []}, direct=phase(), rag=phase(),
                      source_path_hit_at_5=None)
        write_json(folder / f"{q['id']}.json", record)
        records.append(record)
    progress(f"Evidence: {folder}")
    for q, record in zip(questions, records, strict=True):
        path = folder / f"{q['id']}.json"

        def save():
            write_json(path, record)

        progress(f"{q['id']} QUESTION: {q['question']}")
        if command != "direct":
            retrieval = record["retrieval"]
            retrieval.update(status="unknown", attempted=True,
                             input={"texts": [q["question"]], **EMBEDDING_CONFIG})
            save()  # If interrupted after this checkpoint, outcome stays unknown.
            started = perf_counter()
            try:
                result = embedder.embed([q["question"]])
            except ValueError:
                retrieval.update(status="error", error_code="query_embedding_failed",
                                 provider_outcome="unknown")
            else:
                retrieval["usage"] = result.usage
                try:
                    if len(result.vectors) != 1:
                        raise ValueError("Expected one query embedding")
                    vector_norm(result.vectors[0])
                    retrieval["query_vector"] = result.vectors[0]
                    save()  # Keep the obtained vector/usage even if later search fails.
                    retrieval.update(hits=search(index, result.vectors[0]), status="completed")
                    if q["expected_facts"]:
                        record["source_path_hit_at_5"] = source_path_hit(q, retrieval["hits"])
                except ValueError:
                    retrieval.update(status="error", error_code="invalid_query_vector")
            retrieval["elapsed_seconds"] = perf_counter() - started
            save()
            progress(f"{q['id']} retrieval: {retrieval['status']} ({len(retrieval['hits'])} hits)")
        for mode in ("direct", "rag"):
            if command not in {"eval", mode}:
                continue
            if mode == "rag" and record["retrieval"]["status"] != "completed":
                record[mode]["reason"] = "retrieval_unavailable"
                save()
                continue
            inputs = messages(q["question"], record["retrieval"]["hits"] if mode == "rag" else ())
            branch = record[mode]
            branch.update(status="unknown", attempted=True,
                          messages=[asdict(m) for m in inputs], config=asdict(CONFIG),
                          request=generation_payload(inputs, CONFIG))
            save()
            started = perf_counter()
            # Unexpected exceptions stop the experiment; saved input remains unknown.
            outcome = await SimpleAgent(client, CONFIG).generate(inputs)
            branch.update(status="unknown" if outcome.error_code == "llm_timeout" else outcome.status,
                          outcome=asdict(outcome), usage=asdict(outcome.usage) if outcome.usage else None,
                          observed_output=getattr(client, "observed_output", None),
                          elapsed_seconds=perf_counter() - started)
            save()
            progress(f"{q['id']} {mode}: {branch['status']}")
    run["status"] = "finished"  # Completion of traversal, not semantic/provider success.
    write_json(folder / "run.json", run)
    return folder
