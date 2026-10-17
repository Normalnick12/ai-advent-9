"""Immutable Markdown candidates and one-file, explicitly confirmed persistence."""
import difflib
import os
from pathlib import Path
import re
import tempfile

from . import (TARGET, MAX_DOC, bounded, canonical, clean_text, digest, guard,
               read_json, require, write_json)
from .workspace import Workspace

MARKER = re.compile(r"\[\[(E[0-9a-f]{16})\]\]")


def patch(old, new):
    return "".join(difflib.unified_diff(old.splitlines(keepends=True),
                                        new.splitlines(keepends=True),
                                        fromfile="a/" + TARGET, tofile="b/" + TARGET))


def render(content, evidence, ws):
    require(not re.search(r"!?\[[^\]\n]*\]\([^\n]*\)|<(?:script|iframe|img|a)\b", content, re.I),
            "use_evidence_markers_not_links")
    references = {}
    def substitute(match):
        eid = match[1]
        require(eid in evidence, "unknown_evidence")
        entry = evidence[eid]
        require(entry["path"] in ws.meta["source_hashes"], "citation_must_reference_source")
        raw = bounded(ws.path(entry["path"]))
        lines = raw.decode("utf-8-sig").splitlines()
        a, b = entry["start_line"], entry["end_line"]
        require(1 <= a <= b <= len(lines) and entry["sha256"] == digest(raw)
                and entry["text"] == "\n".join(lines[a-1:b]), "invalid_evidence")
        label = f'{entry["path"]}:L{a}-L{b}'
        link = f'[{label}](../{entry["path"]}#L{a}-L{b})'
        references[eid] = dict(entry, link=link)
        return link
    output = MARKER.sub(substitute, content)
    require("[[" not in output and "]]" not in output, "invalid_evidence_marker")
    require(references, "citations_required")
    return output, references


def stage_file(ws, path, content, expected_hash):
    require(path == TARGET, "write_forbidden")
    ws.assert_initial()
    require(isinstance(content, str) and content.strip(), "invalid_content")
    clean_text(content)
    content = content.replace("\r\n", "\n").replace("\r", "\n")
    if not content.endswith("\n"):
        content += "\n"
    require(len(content.encode("utf-8")) <= MAX_DOC, "document_size_limit")
    current = ws.target_hash()
    require(current == expected_hash, "stale_target")
    if current is not None:
        require((TARGET, current) in ws.reads, "target_must_be_read")
    old = bounded(ws.path(TARGET)).decode("utf-8") if current is not None else ""
    rendered, references = render(content, ws.evidence, ws)
    require(len(rendered.encode("utf-8")) <= MAX_DOC, "document_size_limit")
    require(rendered != old, "no_change")
    payload = dict(version=1, run_id=ws.meta["run_id"], path=TARGET, base_hash=current,
                   base_text=old, content=rendered, content_hash=digest(rendered),
                   source_hashes=ws.meta["source_hashes"], revision=ws.meta["revision"],
                   manifest_hash=ws.meta["manifest_hash"], references=references)
    cid = digest(canonical(payload))
    folder = guard(ws.run / "candidates" / cid, ws.run)
    require(not folder.exists(), "candidate_exists")
    folder.mkdir(parents=True)
    write_json(folder / "candidate.json", payload, exclusive=True)
    (folder / "candidate.md").write_text(rendered, encoding="utf-8", newline="\n")
    (folder / "diff.patch").write_text(patch(old, rendered), encoding="utf-8", newline="\n")
    return dict(candidate_id=cid, path=TARGET, content_sha256=payload["content_hash"],
                diff=str(folder / "diff.patch"), status="staged_not_applied")


def candidate(ws, cid):
    require(isinstance(cid, str) and re.fullmatch("[0-9a-f]{64}", cid), "invalid_candidate_id")
    folder = guard(ws.run / "candidates" / cid, ws.run)
    value = read_json(folder / "candidate.json")
    require(digest(canonical(value)) == cid, "candidate_tampered")
    require(value["run_id"] == ws.meta["run_id"] and value["path"] == TARGET
            and value["source_hashes"] == ws.meta["source_hashes"]
            and value["revision"] == ws.meta["revision"]
            and value["manifest_hash"] == ws.meta["manifest_hash"], "candidate_wrong_snapshot")
    require(bounded(folder / "candidate.md", MAX_DOC) == value["content"].encode("utf-8")
            and value["content_hash"] == digest(value["content"]), "candidate_tampered")
    require(bounded(folder / "diff.patch", 2 * MAX_DOC + 4096).decode("utf-8")
            == patch(value["base_text"], value["content"]), "diff_tampered")
    require((digest(value["base_text"]) if value["base_hash"] is not None else None)
            == value["base_hash"], "invalid_base")
    return value, folder


def review(run, cid):
    ws = Workspace(run)
    value, folder = candidate(ws, cid)
    return f"Run: {ws.meta['run_id']}\nCandidate: {cid}\nTarget: {TARGET}\n\n" + bounded(
        folder / "diff.patch", 2 * MAX_DOC + 4096).decode("utf-8")


def reject(run, cid):
    ws = Workspace(run)
    candidate(ws, cid)
    state = ws.state()
    require(state.get("status") == "awaiting_review" and state.get("candidate_id") == cid,
            "candidate_not_available")
    write_json(ws.run / "decision.json", dict(candidate_id=cid, decision="reject"), exclusive=True)
    ws.set_state(status="rejected", candidate_id=cid)
    ws.assert_initial()
    return dict(status="rejected", candidate_id=cid)


def apply_candidate(run, cid, confirmation):
    ws = Workspace(run)
    value, _ = candidate(ws, cid)
    require(confirmation == cid, "explicit_candidate_confirmation_required")
    state = ws.state()
    target = ws.path(TARGET)
    expected_inventory = dict(ws.meta["initial"], **{TARGET: value["content_hash"]})
    if state.get("status") == "applied" and state.get("candidate_id") == cid:
        require(ws.inventory() == expected_inventory, "applied_content_changed")
        return dict(status="already_applied", candidate_id=cid, sha256=ws.target_hash())
    require(state.get("status") in {"awaiting_review", "applying"}
            and state.get("candidate_id") == cid, "candidate_not_available")
    lock = guard(ws.run / "apply.lock", ws.run)
    try:
        descriptor = lock.open("xb")
    except FileExistsError:
        require(False, "apply_in_progress_or_recovery_required")
    temporary = None
    try:
        ws.assert_sources()
        if state["status"] == "applying":
            # A previous failure must be reconciled before any replacement.
            require(ws.inventory() == expected_inventory, "uncertain_write_inspect_disk")
        else:
            ws.assert_initial()
            require(ws.target_hash() == value["base_hash"], "stale_target")
            write_json(ws.run / "decision.json", dict(candidate_id=cid, decision="approve"),
                       exclusive=True)
            ws.set_state(status="applying", candidate_id=cid)
            raw = value["content"].encode("utf-8")
            if value["base_hash"] is None:
                with ws.path(TARGET).open("xb") as stream:
                    stream.write(raw)
                    stream.flush()
                    os.fsync(stream.fileno())
            else:
                fd, temporary = tempfile.mkstemp(prefix="candidate-", dir=target.parent)
                with os.fdopen(fd, "wb") as stream:
                    stream.write(raw)
                    stream.flush()
                    os.fsync(stream.fileno())
                ws.assert_sources()
                require(ws.target_hash() == value["base_hash"], "stale_target")
                guard(target, ws.root)
                os.replace(temporary, target)
                temporary = None
        require(bounded(ws.path(TARGET), MAX_DOC) == value["content"].encode("utf-8"),
                "write_verification_failed")
        ws.assert_sources()
        require(ws.inventory() == expected_inventory, "unexpected_workspace_change")
        receipt = dict(status="applied", candidate_id=cid, path=TARGET,
                       sha256=ws.target_hash(), sources_unchanged=True)
        write_json(ws.run / "receipt.json", receipt)
        ws.set_state(status="applied", candidate_id=cid)
        return receipt
    finally:
        descriptor.close()
        if temporary is not None:
            Path(temporary).unlink(missing_ok=True)
        lock.unlink(missing_ok=True)
