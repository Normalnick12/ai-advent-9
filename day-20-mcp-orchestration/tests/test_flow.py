"""Synthetic offline traces. No provider, repository or Maven requests."""
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest

DAY = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("day20_verify", DAY / "verify.py")
v = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v)


def summary(data):
    # Independent fixture calculation; never import the server's summarizer.
    raw = (json.dumps(data, sort_keys=True, ensure_ascii=True, separators=(",", ":")) + "\n").encode()
    return {**{k: data[k] for k in v.IDENTITY}, "schema_version": 1,
            "version_count": len(data["versions"]), "last_three": data["versions"][-3:],
            "input_sha256": hashlib.sha256(raw).hexdigest()}


def trace(schedule=("research", "lookup_a", "lookup_b", "summary_b", "summary_a"), negative=False):
    from app.mcp_orchestration_service import payload, PROMPT, Settings
    config = payload(PROMPT, Settings("https://day19.example.org/mcp", "redacted"))
    config["tools"][1]["authorization"] = "[REDACTED]"
    imports = [dict(type="mcp_list_tools", id="import_" + label, server_label=label,
                    tools=[dict(name=n, input_schema={"type": "object"}) for n in sorted(names)])
               for label, names in v.ALLOWED.items()]
    outputs = {}
    source = "https://example.org/synthetic-source"
    excerpts = {key: f"{role}: org.example.{key}:{key}-runtime 1.0. {source}"
                for key, role in (("a", "local storage"), ("b", "background work"))}
    def call(id, label, name, args, out):
        return dict(id=id, type="mcp_call", server_label=label, name=name, status="completed",
                    arguments=json.dumps(args), output=json.dumps({"content": [{"type": "text", "text": out if isinstance(out, str) else json.dumps(out)}], "isError": False}))
    outputs["research"] = call("research", "deepwiki", "ask_wiki_question",
        {"repoName": "android/nowinandroid", "question": "Which artifacts support storage and background work?"},
        "\n".join(excerpts.values()))
    records = []
    for key, role in (("a", "local_storage"), ("b", "background_work")):
        lookup = dict(status="no_versions" if negative else "found", group_id=f"org.example.{key}",
            artifact_id=f"{key}-runtime", source_url=f"https://dl.google.com/dl/android/maven2/org/example/{key}/group-index.xml",
            checked_at="2026-09-25T00:00:00+00:00", lookup_id="lookup-" + key,
            versions=[] if negative else ["1.0", "1.1", "1.2", "2.0"])
        outputs["lookup_" + key] = call("lookup_" + key, "dependency_composition", v.LOOKUP,
            {k: lookup[k] for k in ("group_id", "artifact_id")}, lookup)
        outputs["summary_" + key] = call("summary_" + key, "dependency_composition", v.SUMMARY, {"lookup": lookup}, summary(lookup))
        records.append(dict(role=role, group_id=lookup["group_id"], artifact_id=lookup["artifact_id"],
            declared_version="1.0", repository_excerpt=excerpts[key], source_url=source, revision=None,
            lookup_id=lookup["lookup_id"], status=lookup["status"], version_count=len(lookup["versions"]),
            last_three=lookup["versions"][-3:], explanation="Synthetic fixture only"))
    events = []
    for id in schedule:
        events += [dict(type="response.mcp_call.in_progress", item_id=id),
                   dict(type="response.output_item.done", item=outputs[id])]
    final = dict(type="message", id="answer", content=[dict(type="output_text",
        text=json.dumps(dict(branches=records[::-1], conclusion="Synthetic comparison, not a live result")))])
    # Deliberately independent of execution order: final array is not a clock.
    response = dict(status="completed", output=imports + list(outputs.values()) + [final])
    return dict(kind="synthetic_fixture", request_configuration=config), response, events


def get_call(response, id):
    return next(c for c in response["output"] if c.get("id") == id)


def status(data):
    return v.verify(*data)["observed_flow"]["status"]


@pytest.mark.parametrize("schedule", [
    ("research", "lookup_a", "lookup_b", "summary_b", "summary_a"),
    ("research", "lookup_a", "summary_a", "lookup_b", "summary_b"),
    ("research", "lookup_b", "summary_b", "lookup_a", "summary_a"),
])
def test_valid_interleavings_and_data_identity(schedule):
    result = v.verify(*trace(schedule))
    assert result["observed_flow"]["status"] == result["final_facts"]["status"] == "PASS"
    assert result["branches"][0]["summary_call"] == "summary_a"
    assert result["source_truth"]["status"] == "NOT_PROVEN"
    assert all(b["declared_publication"]["published"] is True for b in result["branches"])


def test_final_answer_wrong_count_is_separate():
    data = trace()
    item = get_call(data[1], "answer")
    obj = json.loads(item["content"][0]["text"])
    obj["branches"][0]["version_count"] = 133
    item["content"][0]["text"] = json.dumps(obj)
    result = v.verify(*data)
    assert result["observed_flow"]["status"] == "PASS" and result["final_facts"]["status"] == "FAIL"


def test_wrong_server_error_extra_call_remain_visible():
    for mutation in ("server", "error", "extra"):
        data = trace()
        call = get_call(data[1], "summary_a")
        if mutation == "server":
            call["server_label"] = "deepwiki"
        elif mutation == "error":
            call["output"] = json.dumps({"isError": True, "content": []})
        else:
            data[1]["output"].append({**call, "id": "unexpected", "name": "save_dependency_report"})
        result = v.verify(*data)
        assert result["observed_flow"]["status"] == "FAIL"
        assert len(result["calls"]) == (6 if mutation == "extra" else 5)
        assert mutation != "extra" or "save_dependency_report" in v.render(result)


def test_research_without_explicit_coordinates_not_proven():
    data = trace()
    get_call(data[1], "research")["output"] = "Storage and jobs, no exact coordinates."
    assert status(data) == "NOT_PROVEN"


@pytest.mark.parametrize("change", ["middle_version", "timestamp", "cross_branch", "hash", "tail"])
def test_full_transfer_and_summary_facts(change):
    data = trace()
    call = get_call(data[1], "summary_a")
    args = json.loads(call["arguments"])
    if change == "middle_version":
        args["lookup"]["versions"][1] = "corrupted"
    elif change == "timestamp":
        args["lookup"]["checked_at"] = "changed"
    elif change == "cross_branch":
        args = json.loads(get_call(data[1], "summary_b")["arguments"])
    result = summary(args["lookup"])
    if change == "hash":
        result["input_sha256"] = "0" * 64
    if change == "tail":
        result["last_three"].reverse()
    call["arguments"], call["output"] = json.dumps(args), json.dumps(result)
    assert status(data) == "FAIL"


def test_reverse_order_fails_and_missing_boundaries_not_proven():
    assert status(trace(("research", "summary_a", "lookup_a", "lookup_b", "summary_b"))) == "FAIL"
    assert status(trace(("lookup_a", "research", "summary_a", "lookup_b", "summary_b"))) == "FAIL"
    data = trace()
    assert status((data[0], data[1], [])) == "NOT_PROVEN"


def test_missing_branch_complete_vs_incomplete():
    data = trace()
    data[1]["output"] = [c for c in data[1]["output"] if c.get("id") != "summary_b"]
    events = [e for e in data[2] if e.get("item_id", e.get("item", {}).get("id")) != "summary_b"]
    assert status((data[0], data[1], events)) == "FAIL"
    data[1]["status"] = "incomplete"
    assert status((data[0], data[1], events)) == "NOT_PROVEN"


def test_negative_lookup_and_membership():
    result = v.verify(*trace(negative=True))
    assert result["observed_flow"]["status"] == "PASS"
    assert all(b["declared_publication"]["published"] is False for b in result["branches"])


def test_report_offline_missing_files_partial_log_and_no_overwrite(tmp_path):
    data = trace()
    for name, obj in zip(("attempt.json", "response.json"), data):
        (tmp_path / name).write_text(json.dumps(obj), encoding="utf-8")
    (tmp_path / "events.jsonl").write_text("\n".join(json.dumps(e) for e in data[2]), encoding="utf-8")
    target, result = v.save_report(tmp_path)
    text = (target / "report.md").read_text(encoding="utf-8")
    for phrase in ("android/nowinandroid", "ask_wiki_question", "org.example.a:a-runtime",
                   "org.example.b:b-runtime", "Исходный ответ модели", "NOT_PROVEN", "PASS"):
        assert phrase in text
    assert text.index("summarize_dependency_versions — summary_b") < text.index("summarize_dependency_versions — summary_a")
    with pytest.raises(FileExistsError):
        v.save_report(tmp_path)
    (tmp_path / "response.json").unlink()
    with (tmp_path / "events.jsonl").open("a", encoding="utf-8") as f:
        f.write('\n{"partial":')
    result = v.verify(*v.load_attempt(tmp_path))
    assert result["observed_flow"]["status"] == "NOT_PROVEN"
    assert "NOT_PROVEN" in v.render(result)
    assert v.verify({}, {}, [])["observed_flow"]["status"] == "NOT_PROVEN"


def test_cli_requires_live_opt_in():
    result = subprocess.run([sys.executable, str(DAY / "run.py")], capture_output=True, text=True)
    assert result.returncode == 2 and "No request sent" in result.stderr


def test_current_deepwiki_structured_schema():
    data = trace()
    research = get_call(data[1], "research")
    text = v.unpack(research["output"])
    research["output"] = json.dumps({"structuredContent": {"result": text}})
    assert status(data) == "PASS"


def test_overlap_is_not_proven():
    data = trace()
    events = data[2]
    # Research starts, lookup starts, research completes, lookup completes.
    events[1], events[2] = events[2], events[1]
    assert status(data) == "NOT_PROVEN"


def test_pending_summary_output_is_not_proven():
    data = trace()
    data[1]["status"] = "incomplete"
    item = get_call(data[1], "summary_a")
    item["status"], item["output"] = "in_progress", None
    assert status(data) == "NOT_PROVEN"


def test_extra_research_is_allowed_and_preserved():
    data = trace()
    first = get_call(data[1], "research")
    extra = {**first, "id": "clarify"}
    data[1]["output"].insert(0, extra)
    data[2].extend([dict(type="response.mcp_call.in_progress", item_id="clarify"),
                   dict(type="response.output_item.done", item=extra)])
    result = v.verify(*data)
    assert result["observed_flow"]["status"] == "PASS" and len(result["calls"]) == 6
