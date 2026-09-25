"""Small offline Day 20 verifier. No network or production summary imports."""
import argparse
import hashlib
import json
from pathlib import Path
import re

RESEARCH = {"read_wiki_structure", "read_wiki_contents", "ask_wiki_question"}
LOOKUP, SUMMARY = "get_google_maven_versions", "summarize_dependency_versions"
ALLOWED = {"deepwiki": RESEARCH, "dependency_composition": {LOOKUP, SUMMARY}}
IDENTITY = ("status", "group_id", "artifact_id", "source_url", "checked_at", "lookup_id")
ROLES = {"local_storage", "background_work"}


def canonical(obj):
    return (json.dumps(obj, ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()


def same(a, b):
    return canonical(a) == canonical(b)


def expected(lookup):
    return {**{k: lookup[k] for k in IDENTITY}, "schema_version": 1,
            "version_count": len(lookup["versions"]), "last_three": lookup["versions"][-3:],
            "input_sha256": hashlib.sha256(canonical(lookup)).hexdigest()}


def verdict(status, reason):
    return {"status": status, "reason": reason}


def check(ok, reason):
    return verdict("PASS" if ok else "FAIL", reason)


def reduce_checks(checks):
    states = [v["status"] for v in checks]
    return "FAIL" if "FAIL" in states else "NOT_PROVEN" if not states or "NOT_PROVEN" in states else "PASS"


def unpack(value):
    """Only the native MCP text/structured envelopes used by these endpoints."""
    try:
        obj = json.loads(value) if isinstance(value, str) else value
    except json.JSONDecodeError:
        return value
    if isinstance(obj, dict):
        if obj.get("isError") or obj.get("is_error"):
            raise ValueError("MCP tool error")
        for key in ("structuredContent", "structured_content"):
            if obj.get(key) is not None:
                return obj[key]
        if "content" in obj:
            text = "\n".join(p["text"] for p in obj["content"] if p.get("type") == "text")
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                return text
    return obj


def load_attempt(folder):
    folder = Path(folder)
    issues, events = [], []
    def read(name, default):
        try:
            return json.loads((folder / name).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            issues.append("missing/unreadable " + name)
            return default
    attempt = read("attempt.json", {})
    response = read("response.json", {})
    try:
        for line in (folder / "events.jsonl").read_text(encoding="utf-8").splitlines():
            try:
                events.append(json.loads(line))
            except ValueError:
                issues.append("incomplete event log; no recovery attempted")
                break
    except OSError:
        issues.append("event log unavailable")
    return attempt, response, events, issues


def verify(attempt, response, events, issues=()):
    terminal = response.get("status") == "completed"
    missing = lambda why: verdict("FAIL" if terminal and not issues else "NOT_PROVEN", why)
    items = list(response.get("output", []))
    ids = {i.get("id") for i in items}
    for event in events:
        if event.get("type") == "response.output_item.done":
            item = event.get("item", {})
            if item.get("id") not in ids:
                items.append(item)
                ids.add(item.get("id"))
    for event in events:
        if event.get("type") == "response.output_item.added":
            item = event.get("item", {})
            if item.get("id") not in ids:
                items.append(item)
                ids.add(item.get("id"))
    calls = [i for i in items if i.get("type") == "mcp_call"]
    imports = [i for i in items if i.get("type") == "mcp_list_tools"]
    config = attempt.get("request_configuration", {})
    servers = config.get("tools", [])
    registry = {s.get("server_label"): s for s in servers}
    registered = (len(servers) == 2 and set(registry) == set(ALLOWED)
                  and registry["deepwiki"].get("server_url") == "https://mcp.deepwiki.com/mcp"
                  and registry["dependency_composition"].get("server_url", "").startswith("https://")
                  and len({s.get("server_url") for s in servers}) == 2
                  and all(s.get("type") == "mcp" and set(s.get("allowed_tools", [])) == ALLOWED[s["server_label"]] for s in servers)
                  and config.get("tool_choice") == "auto")
    checks = {"registration": check(registered, "two independent descriptors, allowlists and auto") if config else verdict("NOT_PROVEN", "configuration unavailable")}
    imported = {}
    for label, names in ALLOWED.items():
        found = [i for i in imports if i.get("server_label") == label]
        imported[label] = {t.get("name") for i in found for t in i.get("tools", [])}
        checks["import_" + label] = (check(imported[label] == names and not any(i.get("error") for i in found),
                                                "native tool definitions") if found else missing("no native discovery"))
    starts, ends = {}, {}
    for pos, event in enumerate(events):
        if event.get("type") == "response.mcp_call.in_progress":
            starts.setdefault(event.get("item_id"), pos)
        if event.get("type") == "response.output_item.done" and event.get("item", {}).get("type") == "mcp_call":
            ends.setdefault(event["item"].get("id"), pos)
    def order(parent, child):
        a, b = ends.get(parent.get("id")), starts.get(child.get("id"))
        if a is None or b is None:
            return verdict("NOT_PROVEN", "missing lifecycle boundary; array order is insufficient")
        if a < b:
            return check(True, "observed Responses runtime dependency order")
        parent_start, child_end = starts.get(parent.get("id")), ends.get(child.get("id"))
        if parent_start is not None and child_end is not None and child_end < parent_start:
            return check(False, "downstream completed before upstream started")
        return verdict("NOT_PROVEN", "overlapping/ambiguous lifecycle boundaries")
    parsed, call_checks = {}, []
    for call in calls:
        label, name = call.get("server_label"), call.get("name")
        try:
            if name not in ALLOWED.get(label, set()) or (imported.get(label) and name not in imported[label]):
                raise ValueError("unexpected server/tool or tool not imported")
            if call.get("error") or call.get("status") == "failed":
                raise ValueError("call error")
            if call.get("output") is None or call.get("status") in ("in_progress", "incomplete"):
                call_checks.append(verdict("NOT_PROVEN", str(call.get("id")) + ": unfinished call"))
                continue
            args = json.loads(call["arguments"])
            out = unpack(call["output"])
            if label == "deepwiki" and isinstance(out, dict) and set(out) == {"result"}:
                out = out["result"]  # current DeepWiki outputSchema, observed via tools/list
            if not isinstance(args, dict):
                raise ValueError("arguments are not an object")
            if label == "deepwiki":
                repo = args.get("repoName")
                if repo != "android/nowinandroid" and repo != ["android/nowinandroid"]:
                    raise ValueError("research targets a different repository")
            elif name == LOOKUP:
                if not isinstance(out, dict) or set(out) != set(IDENTITY) | {"versions"}:
                    raise ValueError("unsupported lookup result")
                if (set(args) != {"group_id", "artifact_id"} or
                    any(args[k] != out[k] for k in args) or not isinstance(out["versions"], list)
                    or any(not isinstance(v, str) for v in out["versions"])
                    or not isinstance(out["lookup_id"], str)):
                    raise ValueError("lookup identity or versions mismatch")
                if out["status"] not in {"found", "group_not_found", "artifact_not_found", "no_versions"}:
                    raise ValueError("unknown lookup status")
                if (out["status"] == "found") != bool(out["versions"]):
                    raise ValueError("lookup status mismatch")
                if out["source_url"] != "https://dl.google.com/dl/android/maven2/" + out["group_id"].replace(".", "/") + "/group-index.xml":
                    raise ValueError("lookup source mismatch")
            else:
                if set(args) != {"lookup"} or not same(out, expected(args["lookup"])):
                    raise ValueError("summary differs from independent computation of actual input")
            parsed[call["id"]] = (args, out)
            call_checks.append(check(True, str(call["id"])))
        except (ValueError, TypeError, KeyError, AttributeError) as exc:
            call_checks.append(verdict("FAIL", str(call.get("id")) + ": " + str(exc)))
    checks["execution"] = verdict(reduce_checks(call_checks), "all observed calls checked")
    labels = {c.get("server_label") for c in calls}
    checks["both_servers_called"] = (check(labels == set(ALLOWED), "actual server labels")
        if labels == set(ALLOWED) or labels - set(ALLOWED) else missing("calls from both servers not observed"))
    research = [c for c in calls if c.get("server_label") == "deepwiki" and c.get("id") in parsed]
    lookups = [c for c in calls if c.get("server_label") == "dependency_composition" and c.get("name") == LOOKUP]
    summaries = [c for c in calls if c.get("server_label") == "dependency_composition" and c.get("name") == SUMMARY]
    checks["two_branches"] = (check(len(lookups) == len(summaries) == 2, "two lookups and two summaries; extras remain visible")
                               if terminal else verdict("NOT_PROVEN", "run not completed"))
    branches, branch_checks = [], []
    seen = set()
    for call in lookups:
        if call.get("id") not in parsed:
            continue
        args, out = parsed[call["id"]]
        coord = out["group_id"] + ":" + out["artifact_id"]
        unique = coord not in seen
        seen.add(coord)
        # Match one explicit Maven coordinate; no semantic/source parsing.
        pattern = re.compile(r"(?<![\w.:-])" + re.escape(coord) + r"(?![\w.-])")
        sources = []
        for r in research:
            value = parsed[r["id"]][1]
            text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
            match = pattern.search(text)
            if match:
                sources.append((r, text[max(0, match.start()-160):match.end()+240]))
        related = []
        for s in summaries:
            try:
                obj = json.loads(s.get("arguments", "{}")).get("lookup", {})
                if obj.get("lookup_id") == out["lookup_id"]:
                    related.append(s)
            except (ValueError, AttributeError):
                pass
        sources.sort(key=lambda pair: ends.get(pair[0].get("id"), float("inf")))
        own = {"distinct_dependency": check(unique, "coordinate used once"),
               "research_to_lookup": check(True, "explicit coordinate in raw research") if sources else verdict("NOT_PROVEN", "no explicit coordinate in research"),
               "research_order": order(sources[0][0], call) if sources else verdict("NOT_PROVEN", "no research boundary")}
        summary = related[0] if len(related) == 1 else None
        if summary:
            summary_args = json.loads(summary["arguments"])
            own["lookup_to_summary"] = check(same(summary_args, {"lookup": out}), "full result of this lookup")
            own["summary_order"] = order(call, summary)
            value = parsed.get(summary.get("id"), (None, None))[1]
            own["summary_facts"] = check(same(value, expected(out)), "independent count/last_three/hash") if value is not None else missing("summary output unavailable")
        else:
            for key in ("lookup_to_summary", "summary_order", "summary_facts"):
                own[key] = missing("missing or ambiguous summary for lookup_id")
        branch_checks.extend(own.values())
        branches.append({"coordinates": coord, "lookup_id": out["lookup_id"], "lookup_call": call["id"],
                         "summary_call": summary.get("id") if summary else None,
                         "research_call": sources[0][0]["id"] if sources else None,
                         "research_excerpt": sources[0][1] if sources else None,
                         "facts": expected(out), "checks": own})
    parts = [p["text"] for i in items if i.get("type") == "message" for p in i.get("content", [])
             if p.get("type") == "output_text"]
    final_text = "\n".join(parts) if parts else None
    final = missing("no final answer")
    if final_text is not None:
        try:
            answer = json.loads(final_text)
            records = answer["branches"]
            if len(records) != 2 or {r["role"] for r in records} != ROLES or len(branches) != 2:
                raise ValueError("expected two distinct roles and two branches")
            used = set()
            for record in records:
                matches = [b for b in branches if b["lookup_id"] == record.get("lookup_id")]
                if len(matches) != 1 or record["lookup_id"] in used:
                    raise ValueError("final branch identity mismatch")
                used.add(record["lookup_id"])
                branch = matches[0]
                facts = branch["facts"]
                version = record.get("declared_version")
                research_text = parsed.get(branch["research_call"], (None, ""))[1]
                research_text = research_text if isinstance(research_text, str) else json.dumps(research_text, ensure_ascii=False)
                excerpt, source, revision = (record.get(k) for k in ("repository_excerpt", "source_url", "revision"))
                provenance = (isinstance(excerpt, str) and bool(excerpt) and excerpt in research_text
                    and branch["coordinates"] in excerpt
                    and (source is None or isinstance(source, str) and source in research_text)
                    and (revision is None or isinstance(revision, str) and revision in research_text))
                branch["repository_claim"] = dict(role=record["role"], declared_version=version, explanation=record.get("explanation"),
                    source_url=source, revision=revision,
                    provenance=check(provenance, "final excerpt/link/revision occur in observed research"))
                versions = parsed[branch["lookup_call"]][1]["versions"]
                observed_version = provenance and isinstance(version, str) and version in excerpt
                branch["declared_publication"] = dict(status="PASS" if observed_version else "NOT_PROVEN",
                    declared_version=version, published=version in versions if observed_version else None,
                    reason="membership only; repository usage/revision not independently verified")
                if any(not same(record.get(k), facts[k]) for k in ("group_id", "artifact_id", "status", "version_count", "last_three")):
                    raise ValueError("final facts differ from actual lookup")
            final = check(True, "two roles and publication facts match; repository truth not assessed")
        except (ValueError, TypeError, KeyError):
            final = verdict("FAIL", "final JSON/roles/publication facts mismatch")
    checks["evidence"] = verdict("NOT_PROVEN" if issues else "PASS", "; ".join(issues) if issues else "available records read")
    return {"observed_flow": verdict(reduce_checks([*checks.values(), *branch_checks]), "runtime flow, not source truth"),
            "checks": checks, "branches": branches, "call_checks": call_checks, "calls": calls,
            "lifecycle": {c.get("id"): {"start": starts.get(c.get("id")), "end": ends.get(c.get("id"))} for c in calls},
            "final_facts": final, "final_text": final_text,
            "source_truth": verdict("NOT_PROVEN", "DeepWiki truth/revision and semantic dependency roles not independently established"),
            "evidence_kind": attempt.get("kind", "provider_attempt"), "prompt": config.get("input", ""), "servers": {k: s.get("server_url") for k, s in registry.items()}}


def render(result):
    lines = ["# Day 20 — наблюдаемый developer-flow", "", "> Отчёт приложения по сохранённому evidence. Не новый ответ модели.", "",
             "## Инженерная задача", "", result["prompt"], "", "## Переход между системами", "",
             "Исследование repository нужно для выбора зависимостей; Google Maven — для проверки публикаций.",
             "Ниже фактические calls; объяснение назначения не является скрытым рассуждением модели.", ""]
    if result["evidence_kind"] == "synthetic_fixture":
        lines.insert(2, "> SYNTHETIC OFFLINE FIXTURE — не live и не реальные зависимости repository.\n")
    observed = sorted(result["calls"], key=lambda c: result["lifecycle"][c.get("id")]["start"]
                      if result["lifecycle"][c.get("id")]["start"] is not None else float("inf"))
    for n, call in enumerate(observed, 1):
        bounds = result["lifecycle"][call.get("id")]
        lines.append(f'{n}. {call.get("server_label")} / {call.get("name")} — {call.get("id")} (events: {bounds["start"]} → {bounds["end"]})')
    lines += ["", "Calls упорядочены по наблюдаемому началу; без start event показаны в конце. Номера events отсчитываются от нуля. Завершение и зависимости проверены отдельно.", ""]
    lines += [f'- {v["status"]}: {v["reason"]}' for v in result["call_checks"]]
    lines += ["", "## Инженерный результат", "",
              "| Роль по ответу модели | Координаты | Статус Maven | Количество |",
              "|---|---|---|---|"]
    for branch in result["branches"]:
        fact = branch["facts"]
        lines.append(f'| {branch.get("repository_claim", {}).get("role", "не получена")} | {branch["coordinates"]} | {fact["status"]} | {fact["version_count"]} |')
    lines += ["", "Это сводка сохранённых публикаций, не рекомендация обновления.", "", "## Две dependency-ветки", ""]
    for b in result["branches"]:
        f = b["facts"]
        lines += [f'### {b["coordinates"]}', "",
                  f'Research: {b["research_call"]}; lookup: {b["lookup_call"]}; summary: {b["summary_call"]}.', "",
                  "Наблюдавшийся фрагмент research:", "", "> " + (b["research_excerpt"] or "NOT_PROVEN").replace("\n", "\n> "), "",
                  f'Публикации: {f["status"]}; количество: {f["version_count"]}; последние элементы: {", ".join(f["last_three"]) or "нет"}.', ""]
        claim, publication = b.get("repository_claim", {}), b.get("declared_publication", {})
        lines += [f'Роль по ответу модели: {claim.get("role", "не получена")}. Объявленная версия: {claim.get("declared_version")}.',
                  f'Объяснение модели: {claim.get("explanation") or "не получено"}.',
                  f'Источник: {claim.get("source_url")}; revision: {claim.get("revision")}.',
                  f'Происхождение цитаты/ссылки в research: {claim.get("provenance", {}).get("status", "NOT_PROVEN")}.',
                  f'Членство объявленной версии в полученных публикациях: {publication.get("status", "NOT_PROVEN")}; published={publication.get("published")}.',
                  "Использование этой версии в исходниках независимо не подтверждено.", ""]
        lines += [f'- {key}: **{v["status"]}** — {v["reason"]}' for key, v in b["checks"].items()]
        lines.append("")
    lines += ["## Независимая проверка", "", f'Наблюдаемый flow: **{result["observed_flow"]["status"]}**.',
              f'Финальные факты модели: **{result["final_facts"]["status"]}** — {result["final_facts"]["reason"]}.', ""]
    lines += [f'- {key}: {v["status"]} — {v["reason"]}' for key, v in result["checks"].items()]
    lines += ["", "## Исходный ответ модели", "", result["final_text"] or "Ответ не получен.", "",
              "## Ограничения", "", "Repository truth/revision и смысловая роль зависимости: NOT_PROVEN.",
              "Цитата подтверждает наблюдавшиеся данные, но не их истинность и не источник внутренних знаний модели.",
              "Порядок относится к Responses runtime, не серверным журналам. Публикация не означает совместимость, безопасность или latest/stable.",
              "Это одна попытка. Дополнительные calls не удалены. Отчёт сохранён локально приложением, не MCP save.", ""]
    return "\n".join(lines)


def save_report(folder, output=None):
    result = verify(*load_attempt(folder))
    destination = Path(output) if output else Path(folder) / "review"
    destination.mkdir(parents=True, exist_ok=False)
    (destination / "verdict.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (destination / "report.md").write_text(render(result), encoding="utf-8")
    return destination, result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Offline review only; no model or MCP calls.")
    parser.add_argument("attempt")
    parser.add_argument("--output", help="New review directory; existing files are never overwritten")
    args = parser.parse_args()
    target, result = save_report(args.attempt, args.output)
    print(target / "report.md")
    print("Flow:", result["observed_flow"]["status"], "| Final:", result["final_facts"]["status"])
