"""Read saved evidence only: neither credentials nor a corpus are required."""
import json
from pathlib import Path


def read(path, default=None):
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else default


def render(folder, *, video=False):
    folder = Path(folder)
    manifest = read(folder / 'manifest.json')
    if manifest is None:
        raise ValueError('Saved manifest is required')
    run = read(folder / 'run.json', {})
    review = read(folder / 'review.json', {})
    if review and (review.get('run_id') != manifest['run_id']
                   or review.get('scenario_hash') != manifest['scenario_hash']):
        raise ValueError('Review does not belong to this frozen experiment')
    lines = [f'# Day 25 — {"video" if video else "evidence"} report', '',
             f'Run: {manifest["run_id"]}; execution: {run.get("status", "unknown")}.',
             f'Scenario SHA256: {manifest["scenario_hash"]}',
             f'Corpus: {manifest["index"]["run_id"]}', '', manifest['limitation'], '']
    lines += [f'Reviewer: {review.get("reviewer") or "pending"}.',
              f'Human review: {review.get("human_review_status", "pending")}.', '']
    totals = dict(retrieval=0, generation=0)
    for scenario in manifest['scripts']['scenarios']:
        name = scenario['id']
        summary = run.get('scenarios', {}).get(name, {})
        manual = review.get('scenarios', {}).get(name, {})
        records = {n: read(folder / f'{name}{n}.json', {}) for n in range(1, 7)}
        calls = {key: sum(bool(r.get(key, {}).get('attempted')) for r in records.values())
                 for key in totals}
        for key in totals:
            totals[key] += calls[key]
        lines += [f'## {name}: {scenario["title"]}', '',
            f'Execution: {summary.get("status", "unknown")}; '
            f'mechanical: {summary.get("mechanical_status", "unavailable")}; '
            f'manual: {manual.get("status", "pending")}.',
            f'Calls: embeddings={calls["retrieval"]}, combined generations={calls["generation"]} '
            '(attempted dispatches; unknown outcomes are included).',
            f'Reopen after T3: {summary.get("reopen", {}).get("status", "unavailable")}.', '',
            f'U1: {scenario["turns"][0]["user"]}', f'U2: {scenario["turns"][1]["user"]}', '',
            'Frozen early expectations:']
        lines += ['- ' + ' / '.join(e['fragments']) + f' (U{e["source_user_turn"]})'
                  for e in scenario['early_memory']]
        lines += ['', '| Turn | Outcome | Commit | Memory | Grounding |',
            '| --- | --- | --- | --- | --- |']
        for n, record in records.items():
            lines += [f'| {name}{n} | {record.get("grounded", {}) and record["grounded"].get("status") or record.get("status", "unavailable")} '
                f'| {record.get("commit_status", "unavailable")} '
                f'| {record.get("memory_update_status", "unavailable")} '
                f'| {record.get("grounded_validation", {}).get("status", "unavailable")} |']
        late = records[6]
        actual = late.get('actual_model_context') or {}
        recent = actual.get('recent_history')
        lines += ['', f'U6: {scenario["turns"][5]["user"]}',
            'Actual recent positions (0-based): ' + (str([m['position'] for m in recent])
                if recent is not None else 'unavailable; no captured generation request'),
            f'Excluded positions: {late.get("excluded_positions", "unavailable")}',
            '', 'Task memory before U6:']
        memory = late.get('before', {}).get('memory')
        if memory is None:
            lines += ['unavailable']
        else:
            for field, group in memory.items():
                group = [group] if field == 'goal' and group else [] if field == 'goal' else group
                lines += [f'- {field}: {item["text"]} '
                    f'(U{item["source_user_turn"]}, [{item["source_start"]}, {item["source_end"]}))'
                    for item in group] or [f'- {field}: empty']
        query = (late.get('retrieval', {}).get('input') or {}).get('texts')
        lines += ['', 'Actual embedding input:', '', '```text',
                  query[0] if query else 'unavailable', '```', '', 'Retrieved sources at U6:']
        hits = late.get('retrieval', {}).get('hits', [])
        lines += [f'- {h["source"]} — {h["section"]} (score={h["score"]:.4f}; '
                  f'{h["chunk_id"]})' for h in hits] or ['unavailable']
        grounded = late.get('grounded')
        lines += ['', 'Grounded answer at U6:', '', grounded['answer'] if grounded else 'unavailable']
        if grounded:
            lines += ['', 'Answer sources:']
            lines += [f'- {s["source"]} — {s["section"]} ({s["chunk_id"]})'
                      for s in grounded['sources']] or ['empty (abstention)']
            lines += ['', 'Citations:']
            lines += [f'- {c["chunk_id"]}: {c["quote"]}' for c in grounded['citations']] or ['empty']
        lines += ['', 'Mechanical criteria:']
        checks = summary.get('mechanical', {})
        lines += [f'- {key}: {value}' for key, value in checks.items()
                  if key not in ('early_items', 'manual_review')] or ['unavailable']
        for key, expected in checks.get('early_items', {}).items():
            lines += [f'- early item {key}: {"present" if expected["present"] else "MISSING"}']
        lines += ['', 'Manual review (separate from mechanical checks):',
            f'- Early patch semantics: {manual.get("early_patch_semantics", "pending")}',
            f'- Notes: {manual.get("notes", "pending")}']
        for n in (5, 6):
            verdict = manual.get('turns', {}).get(str(n), {})
            lines += [f'- {name}{n}: relevance={verdict.get("retrieval_relevance", "pending")}; '
                f'citation support={verdict.get("answer_supported_by_citations", "pending")}; '
                f'early constraints={verdict.get("early_constraints_respected", "pending")}; '
                f'assistant repetition={verdict.get("assistant_repetition_channel", "pending")}. '
                f'{verdict.get("notes", "")}']
        if not video:
            lines += ['', 'Full turn evidence (contains actual request, raw result, vectors and chunks):']
            for n in range(1, 7):
                lines += [f'- [{name}{n}.json]({name}{n}.json): ' +
                          '; '.join(scenario['turns'][n-1]['expected_facts'])]
            lines += [f'- [{name}-final.json]({name}-final.json)',
                      f'- [{name}-reopen.json]({name}-reopen.json)']
        lines += ['']
    lines += [f'Total attempted calls: {sum(totals.values())}/24 '
        f'(embeddings={totals["retrieval"]}, generations={totals["generation"]}).',
        'No extraction, rewrite, judge, repair or retry calls. Android demo is separate.',
        'Unknown/partial checkpoints require authoritative reread; they do not prove rollback.', '']
    demo = read(folder / 'android-demo.json')
    if demo:
        lines += ['## Separate Android demonstration', '',
            f'Session: {demo["state"]["session_id"]}; revision: {demo["state"]["revision"]}.',
            f'Calls: {demo["calls"]}. {demo["call_evidence"]}',
            'Verified on emulator: answer, sources and expanded Task Memory with user provenance.',
            'Screenshots: [answer/memory](android-demo.png), [sources/memory](android-demo-sources.png).',
            'This is a UI demonstration, not a replay or replacement of frozen A/B acceptance.',
            'User video recording is not confirmed.', '']
    return '\n'.join(lines)
