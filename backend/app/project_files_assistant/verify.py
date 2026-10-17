"""Offline evidence verifier. Semantic truth is explicitly left for human review."""
import json

from . import (SOURCES, TARGET, FileAgentError, bounded, canonical, digest, read_json, require)
from .changes import candidate, render
from .workspace import Workspace

PROTECTED = """## Область применения

Документ описывает только локальный поиск по подготовленному индексу.
Он не устанавливает SLA и не доказывает качество ответа модели.

"""
EXPECTED_FACTS = [
    "search определена в first_rag/core.py; импортирована и вызвана двумя потребителями выборки",
    "cosine score по убыванию; при равенстве source, ordinal, chunk_id",
    "developer: top_k=len(chunks), первые 8, замена последнего вводным фрагментом при необходимости",
    "support: вопрос + известные observations, top_k=min(2, len(chunks))",
    "полнота ограничена тремя файлами; найденные связи не доказывают охват всего репозитория",
]


def _verify(run):
    ws = Workspace(run)
    state = ws.state()
    require(state.get("candidate_id"), "no_candidate_to_verify")
    value, folder = candidate(ws, state["candidate_id"])
    events = [read for line in bounded(ws.run / "events.jsonl", 8*1024*1024).decode("utf-8").splitlines()
              if (read := json.loads(line))]
    starts = [e for e in events if e["event"] == "start"]
    require(len(starts) == 1 and starts[0]["config"]["tool_choice"] == "auto", "invalid_trace_start")
    requests = [e for e in events if e["event"] == "request"]
    responses = [e for e in events if e["event"] == "response"]
    tools = [e for e in events if e["event"] == "tool"]
    require(len(requests) == len(responses), "incomplete_response_trace")
    native = []
    expected_history = [dict(role="user", content=ws.meta["goal"])]
    cursor = 0
    observed_evidence, read_paths, order = {}, set(), []
    for req, res in zip(requests, responses, strict=True):
        require(req["payload"]["input"] == expected_history
                and req["payload"]["tool_choice"] == "auto"
                and req["payload"]["tools"] == starts[0]["config"]["tools"], "request_chain_mismatch")
        raw = res["response"]
        require(raw.get("status") == "completed", "incomplete_response")
        expected_history.extend(raw["output"])
        for call in (i for i in raw["output"] if i["type"] == "function_call"):
            require(call["call_id"] not in native and cursor < len(tools), "unmatched_call")
            native.append(call["call_id"])
            tool = tools[cursor]
            cursor += 1
            require(tool["call_id"] == call["call_id"] and tool["name"] == call["name"]
                    and tool["arguments"] == call["arguments"], "tool_native_mismatch")
            result = tool["result"]
            expected_history.append(dict(type="function_call_output", call_id=call["call_id"],
                                         output=canonical(result)))
            order.append(call["name"])
            if "error" in result:
                continue
            if call["name"] == "read_file" and result.get("evidence_id"):
                read_paths.add(result["path"])
                observed_evidence[result["evidence_id"]] = dict(
                    path=result["path"], sha256=result["sha256"],
                    start_line=result["start_line"], end_line=result["end_line"],
                    text="\n".join(line["text"] for line in result["lines"]))
            if call["name"] == "search_text":
                for hit in result["matches"]:
                    observed_evidence[hit["evidence_id"]] = dict(path=hit["path"], sha256=hit["sha256"],
                        start_line=hit["line"], end_line=hit["line"], text=hit["text"])
            if call["name"] == "stage_file" and result.get("candidate_id") == state["candidate_id"]:
                args = json.loads(call["arguments"])
                require(args["path"] == TARGET and args["expected_hash"] == value["base_hash"],
                        "candidate_arguments_mismatch")
                rendered, _ = render(args["content"].replace("\r\n", "\n").replace("\r", "\n").rstrip("\n")+"\n",
                                     ws.evidence, ws)
                require(rendered == value["content"], "candidate_not_from_native_call")
    require(cursor == len(tools) and len(native) == len(tools), "unmatched_tool_event")
    require(responses and not any(x["type"] == "function_call"
                                 for x in responses[-1]["response"]["output"]), "missing_final_response")
    require(any(e["event"] == "final" and e.get("candidate_id") == state["candidate_id"]
                for e in events), "missing_final_event")
    for eid, ref in value["references"].items():
        require(eid in observed_evidence, "unobserved_citation")
        require({k: ref[k] for k in observed_evidence[eid]} == observed_evidence[eid],
                "citation_trace_mismatch")
        lines = bounded(ws.path(ref["path"])).decode("utf-8-sig").splitlines()
        a, b = ref["start_line"], ref["end_line"]
        require(ref["sha256"] == digest(bounded(ws.path(ref["path"])))
                and 1 <= a <= b <= len(lines)
                and ref["text"] == "\n".join(lines[a-1:b]), "citation_source_mismatch")
        require(ref["link"] in value["content"], "missing_rendered_link")
    require(set(SOURCES) <= read_paths, "three_sources_not_read")
    searched = any(e["name"] == "search_text" and "error" not in e["result"]
                   and set(SOURCES) <= set(e["result"]["scope"]) for e in tools)
    require("stage_file" in order, "stage_not_observed")
    require(set(SOURCES) <= {r["path"] for r in value["references"].values()}, "three_sources_not_cited")
    if ws.meta["scenario"] == "B":
        require(TARGET in read_paths, "old_document_not_read")
        require(PROTECTED in value["content"], "useful_section_changed")
    ws.assert_sources()
    if state["status"] == "applied":
        require(ws.target_hash() == value["content_hash"], "receipt_disk_mismatch")
        receipt = read_json(ws.run / "receipt.json")
        decision = read_json(ws.run / "decision.json")
        require(receipt["candidate_id"] == state["candidate_id"]
                and receipt["sha256"] == value["content_hash"]
                and decision == dict(candidate_id=state["candidate_id"], decision="approve"), "invalid_write_receipt")
        require(ws.inventory() == dict(ws.meta["initial"], **{TARGET:value["content_hash"]}),
                "unexpected_workspace_change")
        write_status = "PASS"
    else:
        ws.assert_initial()
        write_status = "NOT_APPLIED"
    status = "review_ready" if write_status == "NOT_APPLIED" else "verified_write"
    return dict(status=status if searched else "partial_review",
                candidate_id=state["candidate_id"], native_calls="PASS",
                call_ids=native, tool_order=order, model_calls=len(requests),
                models=sorted({e["response"]["model"] for e in responses}),
                citations="PASS", sources_unchanged="PASS", write=write_status,
                multi_file_search="PASS" if searched else "NOT_OBSERVED",
                acceptance_notes=[] if searched else ["multi_file_search_not_observed"],
                semantic_facts="REVIEW_REQUIRED", facts_checklist=EXPECTED_FACTS,
                diff=str(folder/"diff.patch"), document=str(folder/"candidate.md"),
                provenance_limit="Local trace is inspectable, not a cryptographically signed provider attestation.")


def verify(run):
    try:
        return _verify(run)
    except (FileAgentError, OSError, UnicodeError, ValueError, KeyError, TypeError) as exc:
        code = str(exc) if type(exc) is FileAgentError else type(exc).__name__
        return dict(status="not_proven", native_calls="NOT_PROVEN", write="NOT_PROVEN",
                    semantic_facts="NOT_PROVEN", reason=code)
