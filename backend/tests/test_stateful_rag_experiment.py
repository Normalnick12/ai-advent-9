import asyncio
import json
from copy import deepcopy

import pytest

from app.document_indexing.embedding import DIMENSION, Embeddings
from app.first_rag.core import Index, vector_norm
from app.first_rag.experiment import read_json
from app.llm_client import LlmResult
from app.stateful_rag import experiment
from app.stateful_rag.report import render
from app.stateful_rag.service import EvidenceError
from app.stateful_rag.store import Day25Store


class FakeEmbedder:
    def __init__(self, passed=True):
        self.calls = []
        self.passed = passed

    def embed(self, texts):
        self.calls.append(texts)
        return Embeddings([[1.0 if self.passed else -1.0] + [0.0] * (DIMENSION - 1)], 7)


class FakeClient:
    def __init__(self, scripts, invalid=False):
        self.scripts, self.invalid = scripts, invalid
        self.calls = []

    async def complete(self, messages, config):
        payload = json.loads(messages[0].content)
        self.calls.append(payload)
        assert set(payload) == {'question', 'recent_history', 'task_memory', 'rag_context'}
        assert 'expected_facts' not in messages[0].content
        changes = []
        for scenario in self.scripts['scenarios']:
            for turn in scenario['turns']:
                if turn['user'] != payload['question']:
                    continue
                for early in scenario['early_memory']:
                    if early['source_user_turn'] != turn['turn']:
                        continue
                    start = min(turn['user'].index(f) for f in early['fragments'])
                    end = max(turn['user'].index(f) + len(f) for f in early['fragments'])
                    changes.append(dict(field=early['fields'][0], action='set', item_id=None,
                                        quote=turn['user'][start:end]))
        context = payload['rag_context'][0]
        grounded = dict(status='answered', answer='Fact.',
            sources=[{k: context[k] for k in ('chunk_id', 'source', 'section')}],
            citations=[dict(chunk_id=context['chunk_id'], quote='Fact.')])
        if self.invalid:
            changes.append(dict(field='constraints', action='set', item_id=None, quote='Invented'))
        return LlmResult('completed', reply=json.dumps(dict(grounded=grounded,
            memory_update=dict(changes=changes)), ensure_ascii=False))


@pytest.fixture
def setup(tmp_path):
    scripts = deepcopy(experiment.load_scripts())
    chunks = [dict(chunk_id=f'test-{n}', source='test.md', section='Test', ordinal=n,
        start_line=1, end_line=1, text='Fact. Full chunk body stays outside compact report.',
        embedding=[1.0] + [0.0] * (DIMENSION - 1)) for n in range(5)]
    index = Index(dict(run_id='fixture'), chunks,
                  [vector_norm(c['embedding']) for c in chunks], {'test.md'})
    for scenario in scripts['scenarios']:
        scenario['anchors'] = [{k: chunks[0][k] for k in ('chunk_id', 'source', 'section')}]
        scenario['acceptable_sources'] = ['test.md']
    script_path = tmp_path / 'scripts.json'
    script_path.write_text(json.dumps(scripts, ensure_ascii=False), encoding='utf-8')
    return dict(index=index, client=FakeClient(scripts), embedder=FakeEmbedder(),
                output_root=tmp_path / 'results', scripts_path=script_path, progress=lambda _: None)


def test_frozen_runner_budget_window_memory_reopen_and_keyless_video(setup, monkeypatch):
    folder = asyncio.run(experiment.run_experiment(**setup))
    run = read_json(folder / 'run.json')
    manifest = read_json(folder / 'manifest.json')
    assert run['status'] == 'finished'
    assert run['calls'] == dict(retrieval=12, generation=12)
    assert len(setup['client'].calls) == len(setup['embedder'].calls) == 12
    assert manifest['scenario_hash'] == experiment.sha(setup['scripts_path'].read_bytes())
    for name in ('A', 'B'):
        assert run['scenarios'][name]['mechanical_status'] == 'passed'
        final = read_json(folder / f'{name}-final.json')
        assert len(final['history']) == 12
        record = read_json(folder / f'{name}6.json')
        assert [m['position'] for m in record['actual_model_context']['recent_history']] == list(range(4, 10))
        assert record['actual_model_context']['task_memory'] == record['before']['memory']
        assert setup['embedder'].calls[5 if name == 'A' else 11] == record['retrieval']['input']['texts']
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    monkeypatch.setattr('app.first_rag.core.read_index', lambda **_: pytest.fail('Report reads index'))
    text = render(folder, video=True)
    assert 'manual: pending' in text and 'Total attempted calls: 24/24' in text
    assert 'Full chunk body' not in text and 'query_vector' not in text
    assert 'Actual embedding input' in text and 'Task memory before U6' in text
    assert 'единственной причиной' in text


def test_abstention_continues_but_missing_early_memory_fails_acceptance(setup):
    setup['embedder'].passed = False
    folder = asyncio.run(experiment.run_experiment(**setup))
    run = read_json(folder / 'run.json')
    assert run['status'] == 'finished'
    assert run['calls'] == dict(retrieval=12, generation=0)
    assert not setup['client'].calls
    for summary in run['scenarios'].values():
        assert summary['mechanical_status'] == 'failed'
        assert summary['mechanical']['durable_twelve_messages']
        assert not summary['mechanical']['early_memory']
        assert not summary['mechanical']['late_grounded_answer']
    assert 'MISSING' in render(folder, video=True)


def test_invalid_payload_stops_scenario_without_retry_and_keeps_raw(setup):
    setup['client'].invalid = True
    folder = asyncio.run(experiment.run_experiment(**setup))
    run = read_json(folder / 'run.json')
    assert run['status'] == 'partial'
    assert run['calls'] == dict(retrieval=2, generation=2)
    for name in ('A', 'B'):
        failed = read_json(folder / f'{name}1.json')
        assert failed['generation']['outcome']['reply']
        assert failed['grounded_validation']['status'] == 'passed'
        assert failed['memory_validation']['status'] == 'validation_failed'
        assert failed['commit_status'] == 'not_attempted'
        assert read_json(folder / f'{name}2.json')['status'] == 'not_attempted'
        assert read_json(folder / f'{name}-final.json')['revision'] == 0
    assert 'unavailable; no captured generation request' in render(folder, video=True)


def test_raw_checkpoint_failure_stops_all_calls_before_validation_commit(setup, monkeypatch):
    original = experiment.write_json
    witnessed = []

    def fail_raw(path, record):
        if path.name == 'A1.json' and record.get('generation', {}).get('outcome'):
            witnessed.append(record)
            raise OSError('fixture evidence error')
        original(path, record)

    monkeypatch.setattr(experiment, 'write_json', fail_raw)
    with pytest.raises(EvidenceError):
        asyncio.run(experiment.run_experiment(**setup))
    assert len(setup['client'].calls) == len(setup['embedder'].calls) == 1
    assert witnessed[0]['grounded_validation']['status'] == 'not_run'
    assert witnessed[0]['memory_validation']['status'] == 'not_run'
    assert witnessed[0]['commit_status'] == 'not_attempted'
    folder = next(setup['output_root'].iterdir())
    saved = read_json(folder / 'A1.json')
    assert saved['generation']['status'] == 'unknown'
    assert read_json(folder / 'B1.json')['status'] == 'not_attempted'
    assert 'Total attempted calls: 2/24' in render(folder, video=True)


def test_mismatched_frozen_anchor_rejected_before_calls(setup):
    setup['index'].chunks[0]['section'] = 'Changed'
    with pytest.raises(ValueError, match='anchor'):
        asyncio.run(experiment.run_experiment(**setup))
    assert not setup['client'].calls and not setup['embedder'].calls


def test_final_evidence_failure_never_claims_committed_turn_rolled_back(setup, monkeypatch):
    original = experiment.write_json

    def fail_final(path, record):
        if path.name == 'A1.json' and record.get('commit_status') == 'committed':
            raise OSError('fixture final checkpoint error')
        original(path, record)

    monkeypatch.setattr(experiment, 'write_json', fail_final)
    with pytest.raises(EvidenceError):
        asyncio.run(experiment.run_experiment(**setup))
    folder = next(setup['output_root'].iterdir())
    checkpoint = read_json(folder / 'A1.json')
    assert checkpoint['commit_status'] == 'unknown'
    store = Day25Store(folder / 'A.sqlite3')
    try:
        authoritative = store.read(checkpoint['session_id'])
        assert authoritative['revision'] == 1 and len(authoritative['history']) == 2
    finally:
        store.close()
    assert len(setup['embedder'].calls) == len(setup['client'].calls) == 1
    assert read_json(folder / 'B1.json')['status'] == 'not_attempted'
    assert 'they do not prove rollback' in render(folder, video=True)
