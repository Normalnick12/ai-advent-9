"""Independent read-only verifier. Intentionally imports NO production code.

The short contracts and canonical formula are duplicated to catch shared bugs.
Original evidence is never rewritten; CLI writes a new verdict file exclusively.
"""
import argparse
import base64
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
from uuid import UUID

NAMES = ("get_google_maven_versions", "summarize_dependency_versions", "save_dependency_report")
SERVER = "dependency_composition"
IDENTITY = {"status", "group_id", "artifact_id", "source_url", "checked_at", "lookup_id"}
LOOKUP = IDENTITY | {"versions"}
REPORT = IDENTITY | {"schema_version", "version_count", "last_three", "input_sha256"}
RECEIPT = {"status", "lookup_id", "file_id", "sha256", "bytes"}
FINAL = {"group_id", "artifact_id", "status", "version_count", "last_three", "file_id"}


def loads(value):
    def pairs(items):
        obj = {}
        for key, item in items:
            if key in obj:
                raise ValueError("duplicate_key")
            obj[key] = item
        return obj

    def invalid(value):
        raise ValueError("nonfinite_number")
    return json.loads(value, object_pairs_hook=pairs, parse_constant=invalid)


def canonical(obj):
    return (json.dumps(obj, ensure_ascii=True, sort_keys=True, separators=(",", ":"),
                       allow_nan=False) + "\n").encode("utf-8")


def sha(data):
    return hashlib.sha256(data).hexdigest()


def same(a, b):
    return canonical(a) == canonical(b)  # bool and int cannot compare equal here


def exact(obj, fields):
    if type(obj) is not dict or set(obj) != fields:
        raise ValueError("fields_mismatch")


def pattern(value, expression):
    if type(value) is not str or re.fullmatch(expression, value) is None:
        raise ValueError("invalid_format")


def identifier(value):
    if type(value) is not str or str(UUID(value)) != value:
        raise ValueError("invalid_uuid")


def versions(value):
    if type(value) is not list:
        raise ValueError("invalid_versions")
    for item in value:
        pattern(item, r"\S+")


def coordinates(obj):
    pattern(obj["group_id"], r"[A-Za-z0-9_][A-Za-z0-9_-]*(\.[A-Za-z0-9_][A-Za-z0-9_-]*)*")
    pattern(obj["artifact_id"], r"[A-Za-z0-9_][A-Za-z0-9_.-]*")
    if max(len(obj["group_id"]), len(obj["artifact_id"])) > 256:
        raise ValueError("coordinate_length")


def validate(obj, kind):
    exact(obj,
          {"lookup": LOOKUP, "report": REPORT, "receipt": RECEIPT}[kind])
    identifier(obj["lookup_id"])
    if kind == "receipt":
        pattern(obj["file_id"], r"[0-9a-f]{64}")
        if (obj["status"] != "saved" or obj["sha256"] != obj["file_id"]
                or type(obj["bytes"]) is not int or obj["bytes"] <= 0):
            raise ValueError("invalid_receipt")
        return obj
    coordinates(obj)
    if obj["source_url"] != "https://dl.google.com/dl/android/maven2/" + obj["group_id"].replace(".", "/") + "/group-index.xml":
        raise ValueError("source_mismatch")
    pattern(obj["checked_at"], r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z")
    datetime.strptime(obj["checked_at"], "%Y-%m-%dT%H:%M:%S.%fZ")
    if obj["status"] not in ("found", "group_not_found", "artifact_not_found", "no_versions"):
        raise ValueError("invalid_status")
    if kind == "lookup":
        versions(obj["versions"])
        count = len(obj["versions"])
    else:
        count = obj["version_count"]
        if type(count) is not int or count < 0 or type(obj["schema_version"]) is not int or obj["schema_version"] != 1:
            raise ValueError("invalid_count_or_schema_version")
        versions(obj["last_three"])
        if len(obj["last_three"]) != min(count, 3):
            raise ValueError("tail_length")
        pattern(obj["input_sha256"], r"[0-9a-f]{64}")
    if (obj["status"] == "found") != (count > 0):
        raise ValueError("status_count")
    return obj


def unwrap(raw):
    obj = loads(raw) if isinstance(raw, str) else raw
    if type(obj) is not dict:
        raise ValueError("output_not_object")
    if obj.get("isError") or obj.get("is_error"):
        raise ValueError("tool_error")
    forms = []
    for key in ("structuredContent", "structured_content"):
        if key in obj and obj[key] is not None:
            forms.append(obj[key])
    if "content" in obj:
        content = obj["content"]
        if not isinstance(content, list) or len(content) != 1 or content[0].get("type") != "text":
            raise ValueError("unsupported_content_wrapper")
        forms.append(loads(content[0]["text"]))
    if forms:
        if any(not same(forms[0], value) for value in forms[1:]):
            raise ValueError("contradictory_wrappers")
        return forms[0]
    return obj


def expected(lookup):
    return dict({k: lookup[k] for k in IDENTITY}, schema_version=1,
                version_count=len(lookup["versions"]), last_three=lookup["versions"][-3:],
                input_sha256=sha(canonical(lookup)))


def receipt_for(report):
    data = canonical(report)
    digest = sha(data)
    return dict(status="saved", lookup_id=report["lookup_id"], file_id=digest, sha256=digest, bytes=len(data))


def verdict(status, reason, evidence):
    return dict(status=status, reason=reason, evidence=evidence)


def compare(a, b, reason, evidence):
    return verdict("PASS" if same(a, b) else "FAIL", "exact" if same(a, b) else reason, evidence)


def reduce_status(values):
    states = [v["status"] for v in values]
    return "FAIL" if "FAIL" in states else "NOT_PROVEN" if "NOT_PROVEN" in states else "PASS"


def verify(operation, events, disk):
    calls = operation.get("calls", [])
    ref = ["operation.calls", "server-events.json", "file-read.json"]
    missing = lambda why: verdict("NOT_PROVEN", why, ref)
    results = {key: missing("insufficient_evidence") for key in
               ("tool_execution", "selection_order", "report_correctness", "file_persistence", "final_text_accuracy")}
    transitions = {key: missing("missing_boundary") for key in ("lookup_to_summary", "summary_to_save")}
    parsed, tool_checks = [], []
    for i, call in enumerate(calls):
        try:
            if call.get("error") or call.get("status") not in (None, "completed"):
                raise ValueError("execution_error")
            name = call.get("name")
            if name not in NAMES:
                raise ValueError("unexpected_tool")
            args = loads(call["arguments"])
            result = unwrap(call["output"])
            if name == NAMES[0]:
                exact(args, {"group_id", "artifact_id"})
                coordinates(args)
                validate(result, "lookup")
                check = compare({k: result[k] for k in args}, args, "lookup_identity_mismatch", [f"calls[{i}]"])
            elif name == NAMES[1]:
                exact(args, {"lookup"})
                validate(args["lookup"], "lookup")
                validate(result, "report")
                check = compare(result, expected(args["lookup"]), "summary_actual_input_mismatch", [f"calls[{i}]"])
            else:
                exact(args, {"report"})
                validate(args["report"], "report")
                validate(result, "receipt")
                check = compare(result, receipt_for(args["report"]), "receipt_actual_input_mismatch", [f"calls[{i}]"])
            parsed.append((i, name, args, result))
            tool_checks.append(check)
        except (ValueError, TypeError, KeyError, AttributeError) as exc:
            tool_checks.append(verdict("FAIL", str(exc), [f"calls[{i}]"]))
    if tool_checks:
        results["tool_execution"] = verdict(reduce_status(tool_checks), "actual_inputs_checked", ref)
        if len(calls) < 3 and results["tool_execution"]["status"] == "PASS":
            results["tool_execution"] = missing("missing_tool_execution")
    by_name = {name: next((p for p in parsed if p[1] == name), None) for name in NAMES}
    first, second, third = (by_name[n] for n in NAMES)
    # Every call remains in selection/tool checks. The first observed outputs define
    # source facts; an extra call cannot erase them or turn selection into PASS.
    if first and second:
        transitions["lookup_to_summary"] = compare(second[2], {"lookup": first[3]}, "lookup_transfer_mismatch", ref)
    if second and third:
        transitions["summary_to_save"] = compare(third[2], {"report": second[3]}, "report_transfer_mismatch", ref)
    results["data_transfer"] = dict(verdict(reduce_status(transitions.values()), "both_boundaries", ref), **transitions)
    e = expected(first[3]) if first else None
    if e and second:
        results["report_correctness"] = compare(second[3], e, "report_from_original_lookup_mismatch", ref)
    right_selection = (len(calls) == 3 and [c.get("name") for c in calls] == list(NAMES)
                       and all(c.get("server_label") == SERVER for c in calls))
    if not right_selection:
        results["selection_order"] = verdict("FAIL" if operation.get("invocation") != "unknown" else "NOT_PROVEN",
            "not_called" if not calls else "wrong_count_names_or_server", ref)
    elif first and not same(first[2], {"group_id": "androidx.core", "artifact_id": "core-ktx"}):
        results["selection_order"] = verdict("FAIL", "wrong_target", ref)
    elif len(parsed) == 3:
        matched = []
        for i, name, args, out in parsed:
            ends = [v for v in events if v.get("event") == "tool_end" and v.get("tool") == name
                    and v.get("input_sha256") == sha(canonical(args))
                    and v.get("output_sha256") == sha(canonical(out)) and v.get("outcome") == "completed"
                    and v.get("lookup_id") == out["lookup_id"]]
            if len(ends) != 1:
                break
            end = ends[0]
            starts = [v for v in events if v.get("event") == "tool_start"
                      and v.get("invocation_id") == end.get("invocation_id")
                      and v.get("process_id") == end.get("process_id") and v.get("tool") == name
                      and v.get("input_sha256") == sha(canonical(args))]
            if len(starts) != 1:
                break
            matched.append((starts[0], end))
        if len(matched) == 3:
            flat = [v for pair in matched for v in pair]
            temporal = (len({v.get("process_id") for v in flat}) == 1
                        and len({pair[0].get("invocation_id") for pair in matched}) == 3
                        and all(type(v.get("sequence")) is int and type(v.get("monotonic_ns")) is int for v in flat)
                        and all(a["sequence"] < b["sequence"] and a["monotonic_ns"] < b["monotonic_ns"]
                                for a, b in zip(flat, flat[1:])))
            results["selection_order"] = verdict("PASS" if temporal else "FAIL", "server_temporal_order" if temporal else "overlap_or_order_mismatch", ref)
            upstream = [v for v in events if v.get("event") == "google_maven_lookup"
                        and v.get("invocation_id") == matched[0][0]["invocation_id"]
                        and v.get("lookup_id") == first[3]["lookup_id"]]
            if len(upstream) != 1:
                results["tool_execution"] = missing("upstream_correlation_missing")
            elif (upstream[0].get("outcome") != first[3]["status"]
                  or upstream[0].get("versions_count") != len(first[3]["versions"])
                  or upstream[0].get("source_url") != first[3]["source_url"]):
                results["tool_execution"] = verdict("FAIL", "upstream_event_mismatch", ref)
    confirmed_expected = False
    if disk and disk.get("status") == "read":
        try:
            data = base64.b64decode(disk["base64"], validate=True)
            if (type(disk["bytes"]) is not int or len(data) != disk["bytes"] or sha(data) != disk["sha256"]
                    or disk["file_id"] != sha(data) or disk["operation_id"] != operation["operation_id"]
                    or not disk.get("revision") or not disk.get("read_at")
                    or disk.get("endpoint") != operation["request_configuration"]["tools"][0]["server_url"]):
                raise ValueError("independent_read_metadata_mismatch")
            if e and disk.get("lookup_id") != e["lookup_id"]:
                raise ValueError("file_lookup_identity_mismatch")
            confirmed_expected = e is not None and data == canonical(e)
            if third:
                actual_ok = data == canonical(third[2]["report"])
                if not actual_ok:
                    results["tool_execution"] = verdict("FAIL", "file_actual_input_mismatch", ref)
                results["file_persistence"] = verdict("PASS" if confirmed_expected and actual_ok
                    and same(third[3], receipt_for(e)) else "FAIL", "independent_bytes_compared", ref)
        except (ValueError, TypeError, KeyError) as exc:
            results["file_persistence"] = verdict("FAIL", str(exc), ref)
    elif disk and disk.get("status") == "missing":
        results["file_persistence"] = verdict("FAIL", "file_missing", ref)
    final = operation.get("final_text")
    if final is not None:
        try:
            facts = loads(final)
            exact(facts, FINAL)
            if type(facts["version_count"]) is not int or facts["version_count"] < 0:
                raise ValueError("bad_final_count_type")
            versions(facts["last_three"])
            for key in FINAL - {"last_three", "version_count"}:
                if type(facts[key]) is not str:
                    raise ValueError("bad_final_type")
        except (ValueError, TypeError, KeyError):
            results["final_text_accuracy"] = verdict("FAIL", "final_format_mismatch", ["operation.final_text"])
        else:
            if e:
                expected_final = {k: e[k] for k in FINAL - {"file_id"}}
                expected_final["file_id"] = sha(canonical(e))
                results["final_text_accuracy"] = compare(facts, expected_final, "final_fact_mismatch", ref)
                if results["final_text_accuracy"]["status"] == "PASS" and not confirmed_expected:
                    results["final_text_accuracy"] = missing("expected_file_not_independently_confirmed")
    results["tool_checks"] = tool_checks
    results["chain"] = verdict(reduce_status([results[k] for k in
        ("tool_execution", "selection_order", "data_transfer", "report_correctness", "file_persistence")]), "five_mechanism_verdicts", ref)
    positive = verdict("PASS" if e and e["status"] == "found" else "FAIL" if e else "NOT_PROVEN", "positive_found_scenario", ref)
    results["full_acceptance"] = verdict(reduce_status([results["chain"], results["final_text_accuracy"], positive]), "chain_final_and_found", ref)
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    for name in ("operation", "events", "file_read", "output"):
        parser.add_argument(name)
    args = parser.parse_args()
    result = verify(loads(Path(args.operation).read_text(encoding="utf-8")),
                    loads(Path(args.events).read_text(encoding="utf-8")),
                    loads(Path(args.file_read).read_text(encoding="utf-8")))
    with Path(args.output).open("x", encoding="utf-8") as file:
        json.dump(result, file, indent=2)
        file.write("\n")
    print(json.dumps({k: v["status"] for k, v in result.items() if isinstance(v, dict)}))
