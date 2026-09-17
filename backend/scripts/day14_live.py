"""Explicit Day 14 acceptance: one generation and one controlled conflict, no retries.

Requires a fresh namespace and never resets old data. Writes local evidence after
each operation, including a technical HTTP response; success is not fabricated.
"""
import argparse
import json
import hashlib
import sys
from pathlib import Path

import httpx

# The runner is launched by file path from backend/.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.agent_request import prepare_agent_request
from app.checkout_workflow import CHECKOUT
from app.coding_candidate_adapter import CodingCandidateAdapter
from app.coding_invariants import render_guidance
from app.coding_policy_store import TaskCodingPolicy
from app.invariants_lab_models import CONFIG, ACTIONS
from app.llm_client import AgentConfig, ConversationMessage
from app.openai_agent_payload import generation_payload
from app.profiles import AgentProfile
from app.task_state import TaskState


def approved_request(current, path):
    document = json.loads(path.read_text(encoding="utf-8-sig"))
    assert document["destination"] == "https://api.openai.com/v1/responses"
    approved = document["payload"]
    assert approved["model"] == "gpt-4o-mini"
    profile = AgentProfile.model_validate(current["profile"])
    state = TaskState.model_validate({k: current["task_state"][k] for k in TaskState.model_fields})
    policy = TaskCodingPolicy.model_validate({k: current["policy"][k] for k in TaskCodingPolicy.model_fields})
    prepared = prepare_agent_request(CONFIG, current["memory"], profile, state, CHECKOUT,
        ACTIONS["compatible-retry"][0], invariant_section=render_guidance(policy.values, policy.source))
    adapter = CodingCandidateAdapter(None, prepared)  # Construction only; no generation.
    assert generation_payload(prepared.messages, adapter.config) == approved, "Approved payload mismatch; no dispatch"
    return approved


def run(base_url, output, approved_payload):
    if output.exists():
        raise RuntimeError("Evidence already exists; never overwrite or retry a run")
    output.parent.mkdir(parents=True, exist_ok=True)
    evidence = {"operations": [], "live_happy_path": False}
    def save():
        output.write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
    with httpx.Client(base_url=base_url.rstrip("/") + "/api/v1/invariants/", timeout=90) as api:
        def request(method, path, body=None, *, attempt=False):
            response = api.request(method, path, json=body)
            result = response.json()
            evidence["operations"].append({"method": method, "path": path, "body": body,
                "http_status": response.status_code, "result": result})
            save()
            if not attempt:
                response.raise_for_status()
            return result
        def ref(c):
            return {"task_id": c["memory"]["task_id"], "snapshot_id": c["memory"]["snapshot_id"]}
        def proposal(c, action):
            return request("POST", "proposals", ref(c) | {
                "session_id": c["memory"]["session_id"], "state_revision": c["task_state"]["revision"],
                "profile_id": c["profile"]["profile_id"], "profile_revision": c["profile"]["revision"],
                "binding_revision": c["binding"]["revision"], "policy_id": c["policy"]["policy_id"],
                "policy_version": c["policy"]["definition_version"], "policy_snapshot_id": c["policy"]["snapshot_id"],
                "action_id": action}, attempt=True)

        c = request("GET", "current")
        assert c["memory"] is None, "Fresh Day 14 namespace required; use existing task via UI, no reset"
        request("GET", "scenario")
        c = request("POST", "initialize", {})
        c = request("POST", "setup", ref(c))
        for event in ("REQUIREMENTS_READY", "PLAN_APPROVED"):
            c = request("POST", "events", ref(c) | {"state_revision": c["task_state"]["revision"], "event": event})
        before = c
        assert c["can_propose"] and c["generation_calls"] == 0
        approved = approved_request(c, approved_payload)
        evidence["approved_payload_file_sha256"] = hashlib.sha256(approved_payload.read_bytes()).hexdigest()
        evidence["approved_payload"] = approved
        evidence["approved_payload_matches_preflight"] = True
        evidence["generation_attempt_started"] = True
        save()  # Reserve this single attempt before HTTP; never rerun an uncertain call.
        compatible = proposal(c, "compatible-retry")
        assert compatible.get("observation") and compatible.get("current"), "Unknown outcome; stop without replay"
        first = compatible["observation"]
        assert first["generation_calls"] == 1 and first["actual_request"] is not None
        assert first["assembly_checks"]["status"] == "pass"
        actual = first["actual_request"]
        assert generation_payload(tuple(ConversationMessage(**m) for m in actual["messages"]),
                                  AgentConfig(**actual["config"])) == approved
        evidence["approved_payload_matches_actual"] = True
        save()
        c = compatible["current"]
        conflict = proposal(c, "conflicting-stack")
        assert conflict.get("observation") and conflict.get("current"), "Unknown conflict outcome; stop without replay"
        second = conflict["observation"]
        assert second["generation_calls"] == 0 and second["provider_dispatch"] == "not_dispatched"
        assert second["actual_request"] is None and second["candidate"] is None
        assert second["turn"]["decision"] == "request_refused" and second["turn"]["commit_status"] == "committed"
        assert len(second["turn"]["precheck"]["violations"]) == 3
        final = conflict["current"]
        for key in ("policy", "profile", "binding", "task_state"):
            assert final[key] == before[key]
        for key in ("working", "long_term", "task_id", "session_id"):
            assert final["memory"][key] == before["memory"][key]
        assert final["generation_calls"] == 1
        expected_pairs = int(first["turn"]["commit_status"] == "committed") + 1
        assert len(final["memory"]["short_term"]) == expected_pairs * 2
        assert final["memory"]["short_term"][-1]["content"] == second["turn"]["reply"]
        evidence["live_happy_path"] = first["turn"]["decision"] == "accepted" and first["turn"]["commit_status"] == "committed"
        evidence["checks"] = {"generation_calls": 1, "conflict_calls": 0, "source_preservation": True,
                              "confirmed_pairs": expected_pairs, "no_retries": True}
        save()
        print(json.dumps({"live_happy_path": evidence["live_happy_path"], "checks": evidence["checks"],
                          "compatible": first["turn"], "conflict": second["turn"]}, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--approved-payload", type=Path, required=True)
    args = parser.parse_args()
    run(args.base_url, args.output, args.approved_payload)
