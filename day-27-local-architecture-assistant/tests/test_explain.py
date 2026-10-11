import json

import pytest

from explain import check_inputs, parse_explanation, render, request_bytes
from workspace import Source


def response(payload):
    return {"done": True, "done_reason": "stop", "message": {"content": json.dumps(payload)}}


def valid():
    return {"facts": [{"text": "Класс A", "lines": [1]}], "assumptions": [], "limitations": ["Один файл"]}


def test_payload_and_render():
    body = request_bytes(Source("A.kt", "class A\n\n// end\n"), "Роль?", "test", 8192, 2048, thinking=True)
    payload = json.loads(body)
    assert payload["think"] is False and payload["stream"] is False
    assert payload["options"] == {"num_ctx": 8192, "num_predict": 2048}
    context = json.loads(payload["messages"][1]["content"])
    assert context == {"question": "Роль?", "file": "A.kt", "line_count": 3, "source": "1: class A\n2: \n3: // end"}
    assert "think" not in json.loads(request_bytes(Source("A.kt", "class A"), "?", "test", 8192, 2048, thinking=False))
    parsed = parse_explanation(response(valid()), 3)
    assert "строки 1" in render(parsed) and "Предположения" in render(parsed)


@pytest.mark.parametrize("question,ctx,predict", [("",8192,2048), ("x"*2001,8192,2048), ("?",0,1), ("?",5,5), ("?",8,-1), ("?",True,1)])
def test_invalid_inputs(question, ctx, predict):
    with pytest.raises(ValueError):
        check_inputs(question, ctx, predict)


def test_full_body_limit_includes_line_numbers():
    with pytest.raises(ValueError, match="24 KiB"):
        request_bytes(Source("A.kt", "x\n" * 8000), "?", "test", 8192, 2048, thinking=True)


@pytest.mark.parametrize("lines", [[], [0], [4], [True], ["1"], [1,1], None])
def test_invalid_line_references(lines):
    payload = valid()
    payload["facts"][0]["lines"] = lines
    with pytest.raises(RuntimeError):
        parse_explanation(response(payload), 3)


@pytest.mark.parametrize("payload", [[], {}, {"facts": [], "assumptions": [], "limitations": []},
    {"facts": [{"text": "fact"}], "assumptions": [], "limitations": []},
    {"facts": [], "assumptions": [], "limitations": [" "]},
    {"facts": [], "assumptions": [], "limitations": ["missing"], "extra": 1}])
def test_invalid_schema(payload):
    with pytest.raises(RuntimeError):
        parse_explanation(response(payload), 3)


@pytest.mark.parametrize("patch", [{"done": False}, {"done_reason": "length"}, {"done_reason": None},
    {"done_reason": "unknown"}, {"message": {"thinking": "private", "content": ""}},
    {"message": {"content": "not JSON"}}])
def test_unfinished_never_accepted(patch):
    raw = response(valid()) | patch
    with pytest.raises(RuntimeError):
        parse_explanation(raw, 3)


def test_abstention_and_terminal_controls():
    payload = {"facts": [], "assumptions": [], "limitations": ["Нет данных\x1b[2J\u009b\u202e"]}
    text = render(parse_explanation(response(payload), 1))
    assert "Нет данных" in text
    assert all(c not in text for c in ["\x1b", "\u009b", "\u202e"])
