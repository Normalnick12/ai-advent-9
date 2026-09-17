import json

import pytest

from app.llm_client import AgentConfig, ConversationMessage
from app.openai_agent_payload import generation_payload
from scripts.day14_live import approved_request
from test_invariants_lab import lab, setup, request


@pytest.mark.asyncio
async def test_live_preflight_rejects_any_changed_payload_without_dispatch(lab, tmp_path):
    svc, recording = lab  # Fake client; this test never uses OpenAI.
    setup(svc)
    before = svc.current()
    operation = await svc.propose(request(svc))
    actual = operation["observation"]["actual_request"]
    payload = generation_payload(tuple(ConversationMessage(**m) for m in actual["messages"]),
                                 AgentConfig(**actual["config"]))
    document = {"destination": "https://api.openai.com/v1/responses", "payload": payload}
    path = tmp_path / "approved.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    assert approved_request(before, path) == payload
    payload["max_output_tokens"] += 1
    path.write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(AssertionError, match="Approved payload mismatch"):
        approved_request(before, path)
    assert len(recording.calls) == 1  # Preflight never invokes even the fake client.
