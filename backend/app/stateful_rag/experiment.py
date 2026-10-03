"""Frozen Day 25 A/B experiment; no replay or provider calls during review."""
import hashlib
import json
from copy import deepcopy
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from app.document_indexing.corpus import ROOT
from app.first_rag.experiment import write_json, read_json
from app.grounded_rag.core import THRESHOLD
from .context import CONFIG
from .service import Day25ChatService
from .store import Day25Store

SCENARIOS = ROOT / 'day-25-stateful-rag-chat/scenarios.json'
LIMITATION = ('Наличие ранних user conditions в task memory и embedding input доказывает '
    'механизм. Без ablation оно не доказывает, что memory была единственной причиной '
    'правильного ответа. Exact citations не доказывают semantic support.')


def sha(value):
    return hashlib.sha256(value).hexdigest()


def items(memory):
    return [(field, item) for field, group in memory.items()
            for item in ([group] if field == 'goal' and group else [] if field == 'goal' else group)]


def load_scripts(path=SCENARIOS):
    data = read_json(path)
    if data.get('schema_version') != 1 or [s['id'] for s in data['scenarios']] != ['A', 'B']:
        raise ValueError('Expected frozen scenarios A and B')
    for scenario in data['scenarios']:
        if len(scenario['turns']) != 6 or not scenario['early_memory'] or not scenario['anchors']:
            raise ValueError('Incomplete frozen scenario')
        for number, turn in enumerate(scenario['turns'], 1):
            if turn['turn'] != number or not turn['user'].strip() or not turn['expected_facts']:
                raise ValueError('Invalid frozen turn')
        for expectation in scenario['early_memory']:
            user = scenario['turns'][expectation['source_user_turn'] - 1]['user']
            if not expectation['fragments'] or any(text not in user for text in expectation['fragments']):
                raise ValueError('Early expectation is not from its user turn')
    return data


def review_template(manifest):
    return dict(schema_version=1, run_id=manifest['run_id'],
        scenario_hash=manifest['scenario_hash'], reviewer=None,
        scenarios={s['id']: dict(status='pending', early_patch_semantics='pending',
            notes='', turns={str(t['turn']): dict(status='pending',
                retrieval_relevance='pending', answer_supported_by_citations='pending',
                early_constraints_respected='pending', assistant_repetition_channel='pending',
                facts={f: 'pending' for f in t['expected_facts']}, notes='')
                for t in s['turns']}) for s in manifest['scripts']['scenarios']})


def acceptance(scenario, records, final, reopen):
    """Mechanics only. Semantics belong to the separately saved human review."""
    last = records.get(6)
    result = dict(completed_six_turns=len(records) == 6 and all(
        r.get('commit_status') == 'committed' for r in records.values()),
        durable_twelve_messages=final['revision'] == 6 and len(final['history']) == 12,
        reopen_preserved=reopen.get('status') == 'passed',
        all_answered_grounded=all(
            r.get('grounded', {}).get('status') != 'answered' or
            (r['grounded_validation']['status'] == 'passed'
             and bool(r['grounded']['sources']) and bool(r['grounded']['citations']))
            for r in records.values() if r.get('commit_status') == 'committed'),
        early_durable_history=False, actual_recent_window=False,
        early_memory=False, embedding_contains_early_memory=False,
        late_grounded_answer=False, early_items={}, manual_review='pending')
    if not last:
        return result
    before = last['before']
    first_two = [m for n in (1, 2) for m in (records[n].get('after') or {}).get('history', [])[-2:]]
    result['early_durable_history'] = (len(first_two) == 4 and before['history'][:4] == first_two
        and final['history'][:4] == first_two)
    actual = last.get('actual_model_context') or {}
    recent = actual.get('recent_history')
    result['actual_recent_window'] = (len(before['history']) == 10
        and recent == before['history'][4:10]
        and last.get('excluded_positions') == [0, 1, 2, 3]
        and actual.get('question') == scenario['turns'][5]['user'])
    query = (last.get('retrieval', {}).get('input') or {}).get('texts', [''])[0]
    for expected in scenario['early_memory']:
        matches = []
        for field, item in items(before['memory']):
            source_turn = expected['source_user_turn']
            source_user = scenario['turns'][source_turn - 1]['user']
            if (field in expected['fields'] and item['source_user_turn'] == source_turn
                    and source_user[item['source_start']:item['source_end']] == item['text']
                    and all(fragment in item['text'] for fragment in expected['fragments'])):
                matches.append(dict(field=field, **item, in_embedding_input=item['text'] in query))
        result['early_items'][expected['id']] = dict(present=bool(matches), matches=matches)
    result['early_memory'] = all(e['present'] for e in result['early_items'].values())
    result['embedding_contains_early_memory'] = all(
        any(m['in_embedding_input'] for m in e['matches']) for e in result['early_items'].values())
    grounded = last.get('grounded') or {}
    result['late_grounded_answer'] = (last.get('commit_status') == 'committed'
        and grounded.get('status') == 'answered' and bool(grounded.get('sources'))
        and bool(grounded.get('citations')) and last['grounded_validation']['status'] == 'passed'
        and last['memory_validation']['status'] == 'passed')
    return result


def counts(records):
    return {phase: sum(bool(r.get(phase, {}).get('attempted')) for r in records.values())
            for phase in ('retrieval', 'generation')}


async def run_experiment(*, index, client, embedder, output_root, scripts_path=SCENARIOS,
                         progress=print):
    scripts = load_scripts(scripts_path)
    available = {c['chunk_id']: c for c in index.chunks}
    for scenario in scripts['scenarios']:
        if any(source not in index.sources for source in scenario['acceptable_sources']):
            raise ValueError('Frozen source absent from pinned corpus')
        for anchor in scenario['anchors']:
            if anchor['chunk_id'] not in available or any(
                    available[anchor['chunk_id']][k] != anchor[k] for k in ('source', 'section')):
                raise ValueError('Frozen anchor differs from pinned corpus')
    folder = Path(output_root) / str(uuid4())
    folder.mkdir(parents=True, exist_ok=False)
    source_names = ('context.py', 'models.py', 'store.py', 'service.py', 'experiment.py')
    manifest = dict(schema_version=1, run_id=folder.name,
        created_at=datetime.now(timezone.utc).isoformat(), scripts=deepcopy(scripts),
        scenario_hash=sha(Path(scripts_path).read_bytes()), index=deepcopy(index.provenance),
        config=asdict(CONFIG), threshold=THRESHOLD, recent_pairs=3,
        source_hashes={name: sha(Path(__file__).with_name(name).read_bytes()) for name in source_names},
        query_policy='CURRENT + pre-turn memory by field/stable ID + previous user[:512]; exact dedup',
        call_budget=dict(per_scenario=dict(embeddings=6, generations=6), total=24,
                         extraction=0, rewrite=0, judge=0, retry=0, repair=0), limitation=LIMITATION)
    manifest['config_hash'] = sha(json.dumps(manifest['config'], ensure_ascii=False,
        sort_keys=True).encode('utf-8'))
    # Immutable frozen inputs exist before any provider dispatch.
    write_json(folder / 'manifest.json', manifest)
    write_json(folder / 'review.json', review_template(manifest))
    run = dict(run_id=folder.name, status='partial', scenarios={}, calls=dict(retrieval=0, generation=0))
    for scenario in scripts['scenarios']:
        sid = scenario['id']
        run['scenarios'][sid] = dict(status='not_attempted', confirmed_turns=0,
            reopen=dict(status='not_attempted'), calls=dict(retrieval=0, generation=0))
        for t in scenario['turns']:
            write_json(folder / f'{sid}{t["turn"]}.json', dict(status='not_attempted',
                user=t['user'], retrieval=dict(attempted=False, status='not_attempted'),
                generation=dict(attempted=False, status='not_attempted'), commit_status='not_attempted'))
    write_json(folder / 'run.json', run)
    progress(f'Evidence: {folder}')
    for scenario in scripts['scenarios']:
        name = scenario['id']
        summary = run['scenarios'][name]
        store = Day25Store(folder / f'{name}.sqlite3')
        service = Day25ChatService(store, client, embedder, index)
        state = service.create()
        summary.update(status='partial', session_id=state['session_id'])
        records = {}
        try:
            write_json(folder / 'run.json', run)
            for turn in scenario['turns']:
                number = turn['turn']
                progress(f'{name}{number}: dispatch (no retry)')

                def observe(record):
                    write_json(folder / f'{name}{number}.json', record)

                result = await service.send(state['session_id'], turn['user'], state['revision'],
                                            observe=observe)
                records[number] = result['observation']
                summary['calls'] = counts(records)
                run['calls'] = {key: sum(s['calls'][key] for s in run['scenarios'].values())
                                for key in ('retrieval', 'generation')}
                if not result['response']['committed']:
                    summary['failure_turn'] = number
                    summary['failure_status'] = result['response']['status']
                    write_json(folder / 'run.json', run)
                    progress(f'{name}{number}: {summary["failure_status"]}; scenario stopped')
                    break
                state = result['response']['state']
                summary['confirmed_turns'] = state['revision']
                progress(f'{name}{number}: {result["response"]["grounded"]["status"]}; '
                         f'memory={result["response"]["memory_update_status"]}')
                if number == 3:
                    snapshot = deepcopy(state)
                    store.close()
                    store = Day25Store(folder / f'{name}.sqlite3')
                    service = Day25ChatService(store, client, embedder, index)
                    state = service.read(snapshot['session_id'])
                    summary['reopen'] = dict(status='passed' if state == snapshot else 'failed',
                        revision=state['revision'], provider_calls=0, kind='store_and_service_reopen')
                    write_json(folder / f'{name}-reopen.json', dict(before=snapshot, after=state,
                        **summary['reopen']))
                    if state != snapshot:
                        raise ValueError('Reopen changed authoritative state')
                write_json(folder / 'run.json', run)
            final = service.read(state['session_id'])
            write_json(folder / f'{name}-final.json', final)
            summary['mechanical'] = acceptance(scenario, records, final, summary['reopen'])
            summary['mechanical_status'] = 'passed' if all(v is True for k, v in
                summary['mechanical'].items() if k not in ('early_items', 'manual_review')) else 'failed'
            summary['status'] = 'finished' if summary['mechanical']['completed_six_turns'] else 'partial'
            write_json(folder / 'run.json', run)
        finally:
            store.close()
    run['status'] = 'finished' if all(s['status'] == 'finished' for s in run['scenarios'].values()) else 'partial'
    write_json(folder / 'run.json', run)
    return folder
