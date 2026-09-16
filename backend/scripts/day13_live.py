"""Explicit three-call Day 13 acceptance. Run manually; never part of pytest.

Requires a fresh Day 13 namespace. Stops on failure without retry or cleanup.
Evidence is written after each operation to the requested local JSON file.
"""
import argparse
import json
from pathlib import Path

import httpx


def run(base_url, output):
    evidence = {"operations": [], "semantic_assessment": "pending human review"}
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        raise RuntimeError("Evidence file exists; choose another output, do not overwrite a previous run")
    with httpx.Client(base_url=base_url.rstrip("/") + "/api/v1/task-state/", timeout=90) as api:
        def request(method, path, body=None):
            response = api.request(method, path, json=body)
            result = response.json()
            evidence["operations"].append({"method": method, "path": path, "body": body,
                "http_status": response.status_code, "result": result})
            output.write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
            response.raise_for_status()
            return result

        def current():
            return request("GET", "current")

        def ref(c):
            return {"snapshot_id": c["memory"]["snapshot_id"], "task_id": c["memory"]["task_id"],
                    "state_revision": c["task_state"]["revision"]}

        def event(c, name):
            return request("POST", "events", ref(c) | {"event": name})

        def new_conversation(c):
            after = request("POST", "lifecycle/new-conversation", {"snapshot_id": c["memory"]["snapshot_id"]})
            for key in ("task_id", "working", "long_term", "memory_owner_id"):
                assert after["memory"][key] == c["memory"][key]
            assert after["memory"]["short_term"] == [] and after["memory"]["session_id"] != c["memory"]["session_id"]
            assert after["task_state"] == c["task_state"] and after["profiles"] == c["profiles"] and after["binding"] == c["binding"]
            return after

        def send(c, query):
            p = next(p for p in c["profiles"] if p["profile_id"] == c["binding"]["active_profile_id"])
            op = request("POST", "messages", ref(c) | {"profile_id": p["profile_id"], "profile_revision": p["revision"],
                "binding_revision": c["binding"]["revision"], "message": query})
            o = op["observation"]
            print(json.dumps({"query": query, "state": o["selected_state"], "outcome": o["outcome"]}, ensure_ascii=False), flush=True)
            assert o["outcome"]["status"] == "completed" and o["conversation_committed"]
            assert op["current"]["task_state"] == c["task_state"]
            assert len(op["current"]["memory"]["short_term"]) == len(c["memory"]["short_term"]) + 2
            for level in ("storage_checks", "selection_checks", "assembly_checks"):
                assert all(check["correct"] for check in o[level].values())
            return op

        assert current()["memory"] is None, "Fresh namespace required; no automatic reset"
        scenario = request("GET", "scenario")
        c = request("POST", "initialize", {})
        p = request("POST", "profiles", {"owner_id": c["memory"]["memory_owner_id"], "fields": scenario["profile"]})["profile"]
        c = request("POST", f'profiles/{p["profile_id"]}/select', {"owner_id": p["owner_id"],
            "expected_profile_revision": p["revision"], "expected_binding_revision": 0})
        for key, value in scenario["working"].items():
            c = request("POST", "memory", {"snapshot_id": c["memory"]["snapshot_id"], "layer": "WORKING",
                "key": key, "operation": "set", "value": value})
        assert c["memory"]["long_term"] == {} and c["ready"]
        c = event(event(c, "REQUIREMENTS_READY"), "PLAN_APPROVED")
        assert c["generation_calls"] == 0 and c["task_state"]["state_id"] == "EXECUTION_IMPLEMENT"
        execution = send(c, scenario["execution_query"])
        c = new_conversation(event(execution["current"], "PAUSE"))
        status = send(c, "Где мы остановились?")
        c = new_conversation(status["current"])
        paused = c
        c = event(c, "RESUME")
        assert c["memory"] == paused["memory"] and c["profiles"] == paused["profiles"]
        continuation = send(c, "Продолжим")
        for op in (status, continuation):
            assert op["observation"]["memory"]["short_term"] == []
            # Exact context assembly excludes both inactive transcripts, not just selected markers.
            messages = op["observation"]["request"]["messages"]
            assert len(messages) == 3 and messages[-1]["content"] == op["observation"]["query"]
            assert messages[0]["content"].startswith("LONG_TERM") and messages[1]["content"].startswith("WORKING")
        c = continuation["current"]
        assert c["generation_calls"] == 3 and c["task_state"]["state_id"] == "EXECUTION_IMPLEMENT"
        assert c["task_state"]["status"] == "ACTIVE" and c["task_state"]["revision"] == 4
        c = event(c, "IMPLEMENTATION_READY")
        assert c["generation_calls"] == 3 and c["task_state"]["state_id"] == "VALIDATION_CHECK"
        evidence["formal_acceptance"] = "pass"
        evidence["generation_calls"] = 3
        output.write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
        print("Formal acceptance PASS: 3 generation calls; explicit progress; two inactive transcripts excluded.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    run(args.base_url, args.output)
