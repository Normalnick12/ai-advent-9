from collections import Counter
from pathlib import Path

from app.first_rag.experiment import read_json

FACT_FIELDS = ("expected_fact_in_retrieved_context", "direct_answer_covers_fact", "rag_answer_covers_fact")


def load_report(folder):
    folder = Path(folder)
    run, review = read_json(folder / "run.json"), read_json(folder / "review.json")
    if (review["eval_id"], review["question_hash"]) != (run["eval_id"], run["question_hash"]):
        raise ValueError("Review belongs to another experiment/question set")
    records = {}
    for q in run["questions"]:
        path = folder / f"{q['id']}.json"
        records[q["id"]] = read_json(path) if path.exists() else None
        item = review["questions"][q["id"]]
        if set(item["facts"]) != {f["id"] for f in q["expected_facts"]}:
            raise ValueError("Review fact IDs differ from frozen expectations")
        for values in item["facts"].values():
            if any(values[k] not in {None, "yes", "partial", "no"} for k in FACT_FIELDS):
                raise ValueError("Invalid manual fact label")
        if item["status"] not in {"pending", "reviewed"}:
            raise ValueError("Invalid review status")
        for claim in item["claims"]:
            if claim["grounded_in_retrieved_context"] not in {"yes", "no"}:
                raise ValueError("Invalid groundedness label")
    return run, review, records


def coverage(item, field, *, available=True):
    if not available:
        return "unavailable"
    values = Counter(v[field] or "pending" for v in item["facts"].values())
    return "/".join(f"{k}:{values[k]}" for k in ("yes", "partial", "no", "pending") if values[k]) or "N/A"


def grounded(item, available):
    if not available:
        return "unavailable"
    if item["status"] != "reviewed":
        return "pending"
    return str(dict(Counter(c["grounded_in_retrieved_context"] for c in item["claims"]))) or "N/A"


def render(folder, *, question_id=None, full=False, retrieval_only=False):
    run, review, records = load_report(folder)
    lines = [f"SAVED RUN: {run['eval_id']} | {run['created_at']} | traversal={run['status']}",
             f"Model: {run['config']['model']} | output budget: {run['config']['max_output_tokens']}",
             f"Index: {run['index']}", f"Question set hash: {run['question_hash']}"]
    for name in ("retrieval", "direct", "rag"):
        phases = [r[name] for r in records.values() if r]
        lines.append(f"{name} calls attempted={sum(p['attempted'] for p in phases)}; "
                     f"statuses={dict(Counter(p['status'] for p in phases))}")
    if question_id is None:
        lines.extend(["", "SUMMARY (manual fact counts; source_path_hit@5 is auxiliary)",
                      "ID | difficulty | source_path_hit@5 | context | direct | RAG | grounded | review | technical"])
        for q in run["questions"]:
            r, item = records[q["id"]], review["questions"][q["id"]]
            if r is None:
                lines.append(f"{q['id']} | missing checkpoint / unavailable")
                continue
            availability = [r[k]["status"] == "completed" for k in ("retrieval", "direct", "rag")]
            scores = [coverage(item, f, available=a) for f, a in zip(FACT_FIELDS, availability)]
            hit = r["source_path_hit_at_5"]
            lines.append(" | ".join([q["id"], q["difficulty"], "N/A" if hit is None else str(hit),
                                     *scores, grounded(item, availability[-1]), item["status"],
                                     "/".join(r[k]["status"] for k in ("retrieval", "direct", "rag"))]))
        return "\n".join(lines)
    q = next((q for q in run["questions"] if q["id"] == question_id), None)
    if q is None:
        raise ValueError("Unknown question ID")
    r, item = records[question_id], review["questions"][question_id]
    lines.extend(["", f"QUESTION {question_id}: {q['question']}", "", "RETRIEVED TOP-5"])
    if r is None:
        return "\n".join(lines + ["Checkpoint unavailable; no replay."])
    lines.append(f"Technical status: {r['retrieval']['status']}; query usage: {r['retrieval']['usage']}")
    for c in r["retrieval"]["hits"]:
        lines.extend([f"[S{c['rank']}] cosine={c['score']:.6f} | {c['source']}:{c['start_line']}-{c['end_line']}",
                      f"  section: {c['section']} | chunk: {c['chunk_id']}",
                      c["text"] if full else c["text"][:350] + (" … [--full]" if len(c["text"]) > 350 else "")])
    if retrieval_only:
        return "\n".join(lines)
    for mode in ("direct", "rag"):
        branch = r[mode]
        lines.extend(["", f"{mode.upper()} ANSWER | {branch['status']}",
                      branch.get("outcome", {}).get("reply") or "[No completed answer]",
                      f"Usage: {branch['usage']}"])
        if branch["status"] != "completed":
            lines.append(f"Technical details: {branch.get('outcome', branch.get('reason'))}")
            for output in (branch.get("observed_output") or {}).get("output", []):
                for content in output.get("content", []):
                    if content.get("text"):
                        lines.append("PARTIAL / NOT COMPLETED: " + content["text"])
    lines.extend(["", "EXPECTED FACTS / REVIEW", f"Difficulty: {q['difficulty']} | review: {item['status']}",
                  f"source_path_hit@5: {r['source_path_hit_at_5']} (Q10: N/A)"])
    for fact in q["expected_facts"]:
        values = item["facts"][fact["id"]]
        cells = [values[f] or "pending" if r[mode]["status"] == "completed" else "unavailable"
                 for f, mode in zip(FACT_FIELDS, ("retrieval", "direct", "rag"))]
        lines.extend([f"{fact['id']}: {fact['text']}",
                      f"  context / direct / RAG: {' / '.join(cells)}", f"  {values['notes']}"])
    for claim in item["claims"]:
        lines.append(f"Grounded={claim['grounded_in_retrieved_context']}: {claim['claim']} | {claim.get('notes', '')}")
    lines.extend([f"Diagnosis: {item['diagnosis']}", item["notes"]])
    return "\n".join(lines)
