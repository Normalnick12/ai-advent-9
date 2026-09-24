import base64
import copy
import hashlib
import json
import pytest

import verify as v
from collect import collect
from launch import launch
import httpx


@pytest.fixture
def bundle():
    lookup = dict(status="found", group_id="androidx.core", artifact_id="core-ktx", versions=["6", "1", "6", "3", "4", "5"],
        source_url="https://dl.google.com/dl/android/maven2/androidx/core/group-index.xml", checked_at="2026-09-24T00:00:00.000Z",
        lookup_id="12345678-1234-1234-1234-123456789abc")
    report = v.expected(lookup)
    receipt = v.receipt_for(report)
    arguments = [{"group_id": "androidx.core", "artifact_id": "core-ktx"}, {"lookup": lookup}, {"report": report}]
    outputs = [lookup, report, receipt]
    calls, events = [], []
    for i, (name, args, output) in enumerate(zip(v.NAMES, arguments, outputs)):
        calls.append(dict(id=str(i), type="mcp_call", server_label=v.SERVER, name=name,
                          arguments=json.dumps(args), output=json.dumps(output), status="completed"))
        common = dict(tool=name, invocation_id=str(i), process_id="process", input_sha256=v.sha(v.canonical(args)))
        events.append(dict(common, event="tool_start", sequence=i * 3, monotonic_ns=i * 3))
        events.append(dict(common, event="tool_end", sequence=i * 3 + 2, monotonic_ns=i * 3 + 2,
            output_sha256=v.sha(v.canonical(output)), lookup_id=lookup["lookup_id"], outcome="completed"))
    events.insert(1, dict(event="google_maven_lookup", invocation_id="0", process_id="process", lookup_id=lookup["lookup_id"],
                         outcome="found", versions_count=6, source_url=lookup["source_url"]))
    final = dict({k: report[k] for k in v.FINAL - {"file_id"}}, file_id=receipt["file_id"])
    operation = dict(operation_id="op", invocation="observed", calls=calls, final_text=json.dumps(final),
                     request_configuration={"tools": [{"server_url": "offline"}]})
    disk = dict(status="read", operation_id="op", lookup_id=lookup["lookup_id"], revision="fixture", endpoint="offline",
        read_at="2026-09-24T00:01:00Z", file_id=receipt["file_id"], sha256=receipt["sha256"], bytes=receipt["bytes"],
        base64=base64.b64encode(v.canonical(report)).decode())
    return operation, events, disk


def test_baseline_and_golden(bundle):
    result = v.verify(*bundle)
    assert result["full_acceptance"]["status"] == "PASS", result
    assert v.canonical({"z": "é", "a": ["2", "1", "2"]}) == b'{"a":["2","1","2"],"z":"\\u00e9"}\n'
    assert not v.same(True, 1)


@pytest.mark.parametrize("field,new", [("versions", ["6", "X", "6", "3", "4", "5"]),
    ("versions", ["1", "6", "6", "3", "4", "5"]), ("artifact_id", "core"),
    ("lookup_id", "22345678-1234-1234-1234-123456789abc"), ("checked_at", "2026-09-23T00:00:00.000Z")])
def test_first_boundary_with_correct_tool_for_corrupted_input(bundle, field, new):
    op, events, disk = bundle
    lookup = json.loads(op["calls"][1]["arguments"])["lookup"]
    lookup[field] = new
    report = v.expected(lookup)
    op["calls"][1]["arguments"] = json.dumps({"lookup": lookup})
    op["calls"][1]["output"] = json.dumps(report)
    result = v.verify(op, events, disk)
    assert result["data_transfer"]["lookup_to_summary"]["status"] == "FAIL"
    assert result["tool_checks"][1]["status"] == "PASS"
    assert result["report_correctness"]["status"] == "FAIL"


def test_second_boundary_forgery(bundle):
    op, events, disk = bundle
    report = json.loads(op["calls"][2]["arguments"])["report"]
    report["version_count"] += 1  # schema-valid, save must not repair it
    op["calls"][2]["arguments"] = json.dumps({"report": report})
    op["calls"][2]["output"] = json.dumps(v.receipt_for(report))
    result = v.verify(op, events, disk)
    assert result["data_transfer"]["summary_to_save"]["status"] == "FAIL"
    assert result["tool_checks"][2]["status"] == "PASS"
    assert result["file_persistence"]["status"] == "FAIL"


@pytest.mark.parametrize("mutation", ["bad_hash", "count", "bool", "extra", "duplicate", "wrappers", "source"])
def test_output_mutations(bundle, mutation):
    op, events, disk = bundle
    report = json.loads(op["calls"][1]["output"])
    if mutation == "bad_hash": report["input_sha256"] = "0" * 64
    if mutation == "count": report["version_count"] += 1
    if mutation == "bool": report["schema_version"] = True
    if mutation == "extra": report["path"] = "x"
    if mutation == "source": report["source_url"] = "https://example.org"
    raw = json.dumps(report)
    if mutation == "duplicate": raw = raw[:-1] + ',"schema_version":1}'
    if mutation == "wrappers": raw = json.dumps(dict(structuredContent=report, content=[dict(type="text", text="{}")]))
    op["calls"][1]["output"] = raw
    assert v.verify(op, events, disk)["tool_execution"]["status"] == "FAIL"


@pytest.mark.parametrize("field,new", [("bytes", 1), ("sha256", "0" * 64), ("base64", "eA=="),
    ("operation_id", "other"), ("lookup_id", "other"), ("endpoint", "other"), ("status", "missing")])
def test_disk_mutation(bundle, field, new):
    op, events, disk = bundle
    disk[field] = new
    assert v.verify(op, events, disk)["file_persistence"]["status"] == "FAIL"


def test_unavailable_receipt_and_events(bundle):
    op, events, disk = bundle
    assert v.verify(op, events, None)["file_persistence"]["status"] == "NOT_PROVEN"
    assert v.verify(op, [], disk)["selection_order"]["status"] == "NOT_PROVEN"
    receipt = json.loads(op["calls"][2]["output"])
    receipt["bytes"] += 1
    op["calls"][2]["output"] = json.dumps(receipt)
    assert v.verify(op, events, disk)["tool_execution"]["status"] == "FAIL"


@pytest.mark.parametrize("mode", ["zero", "extra", "reorder", "missing", "wrong_server", "overlap"])
def test_selection(bundle, mode):
    op, events, disk = bundle
    if mode == "zero": op["calls"] = []
    if mode == "extra": op["calls"].append(copy.deepcopy(op["calls"][2]))
    if mode == "reorder": op["calls"].reverse()
    if mode == "missing": op["calls"].pop()
    if mode == "wrong_server": op["calls"][1]["server_label"] = "other"
    if mode == "overlap": events[3]["monotonic_ns"] = 0
    result = v.verify(op, events, disk)
    assert result["selection_order"]["status"] == "FAIL", result
    if mode == "extra": assert result["final_text_accuracy"]["status"] == "PASS"


@pytest.mark.parametrize("final,reason", [("markdown", "final_format_mismatch"), ('{"version_count":6}', "final_format_mismatch"),
                                         (None, "insufficient_evidence")])
def test_final_format(bundle, final, reason):
    op, events, disk = bundle
    op["final_text"] = final
    result = v.verify(op, events, disk)
    assert result["chain"]["status"] == "PASS"
    assert result["final_text_accuracy"]["reason"] == reason


def test_wrong_count_separate_from_chain(bundle):
    op, events, disk = bundle
    final = json.loads(op["final_text"])
    final["version_count"] = 99
    op["final_text"] = json.dumps(final)
    result = v.verify(op, events, disk)
    assert result["chain"]["status"] == "PASS"
    assert result["final_text_accuracy"]["reason"] == "final_fact_mismatch"
    assert result["full_acceptance"]["status"] == "FAIL"


def test_unknown_and_incomplete(bundle):
    op, events, disk = bundle
    unknown = v.verify(dict(invocation="unknown", calls=[]), [], None)
    assert unknown["chain"]["status"] == "NOT_PROVEN"
    op["provider_status"] = "incomplete"
    op["final_text"] = None
    result = v.verify(op, events, disk)
    assert result["chain"]["status"] == "PASS" and result["full_acceptance"]["status"] == "NOT_PROVEN"


def test_collector_lossless_and_path(tmp_path):
    data = b'not JSON\x00\xff\r\n'
    digest = hashlib.sha256(data).hexdigest()
    path = tmp_path / (digest + ".json")
    path.write_bytes(data)
    meta = dict(operation_id="op", lookup_id="id", revision="rev", endpoint="offline", root=tmp_path)
    assert base64.b64decode(collect(digest, **meta)["base64"]) == data
    assert path.read_bytes() == data
    for bad in ("../x", "A" * 64, "0" * 64 + ".json"):
        with pytest.raises(ValueError): collect(bad, **meta)
    assert collect("0" * 64, **meta)["status"] == "missing"
    assert len(list(tmp_path.iterdir())) == 1


def test_launcher_one_post_and_no_reuse(tmp_path):
    calls = []
    def backend(req):
        calls.append(req)
        assert req.method == "POST" and req.url.path == "/api/v1/mcp-composition/run"
        return httpx.Response(200, json={"final_text": "raw", "outcome": "response_received"})
    folder = tmp_path / "attempt"
    assert launch(folder, transport=httpx.MockTransport(backend))["final_text"] == "raw"
    with pytest.raises(FileExistsError): launch(folder, transport=httpx.MockTransport(backend))
    assert len(calls) == 1


def test_launcher_timeout_no_retry(tmp_path):
    calls = []
    def backend(req):
        calls.append(req)
        raise httpx.ReadTimeout("timeout")
    with pytest.raises(httpx.ReadTimeout): launch(tmp_path / "attempt", transport=httpx.MockTransport(backend))
    assert len(calls) == 1
