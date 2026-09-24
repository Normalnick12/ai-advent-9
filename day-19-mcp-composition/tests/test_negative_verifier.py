import base64
import json
import pytest
from test_verifier import bundle
import verify as v


@pytest.mark.parametrize("status", ["group_not_found", "artifact_not_found", "no_versions"])
def test_negative_mechanism_is_not_positive_acceptance(bundle, status):
    op, events, disk = bundle
    first = json.loads(op["calls"][0]["output"])
    first.update(status=status, versions=[])
    report = v.expected(first)
    receipt = v.receipt_for(report)
    args = [json.loads(op["calls"][0]["arguments"]), {"lookup": first}, {"report": report}]
    for index, result in enumerate((first, report, receipt)):
        call = op["calls"][index]
        call["arguments"], call["output"] = json.dumps(args[index]), json.dumps(result)
        for event in events:
            if event.get("tool") == call["name"]:
                event["input_sha256"] = v.sha(v.canonical(args[index]))
                if event["event"] == "tool_end": event["output_sha256"] = v.sha(v.canonical(result))
    events[1].update(outcome=status, versions_count=0)
    disk.update(base64=base64.b64encode(v.canonical(report)).decode(), file_id=receipt["file_id"],
                sha256=receipt["sha256"], bytes=receipt["bytes"])
    op["final_text"] = json.dumps(dict({k: report[k] for k in v.FINAL - {"file_id"}}, file_id=receipt["file_id"]))
    result = v.verify(op, events, disk)
    assert result["chain"]["status"] == "PASS", result
    assert result["full_acceptance"]["status"] == "FAIL"
