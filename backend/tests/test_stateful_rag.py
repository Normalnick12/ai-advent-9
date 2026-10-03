import json
import asyncio
from copy import deepcopy
from uuid import uuid4

import pytest

from app.conversation_store import ConversationStorageError
from app.grounded_rag.core import abstention
from app.stateful_rag.models import ChatError, TaskMemory, reduce_memory
from app.stateful_rag.store import Day25Store
from app.stateful_rag.service import Day25ChatService
from app.document_indexing.embedding import DIMENSION, Embeddings
from app.first_rag.core import Index, vector_norm
from app.llm_client import LlmResult


class FakeEmbedder:
    def __init__(self, score_pass=True):
        self.calls = []
        self.score_pass = score_pass

    def embed(self, texts):
        self.calls.append(texts)
        return Embeddings([[1.0 if self.score_pass else -1.0] + [0.0] * (DIMENSION-1)], 5)


class FakeClient:
    def __init__(self, mode='answer'):
        self.mode, self.calls = mode, []

    async def complete(self, messages, config):
        payload = json.loads(messages[0].content)
        self.calls.append(payload)
        if self.mode in ('refused', 'incomplete', 'error'):
            return LlmResult(self.mode, error_code=self.mode)
        c = payload['rag_context'][0]
        grounded = dict(status='answered', answer='Fact.',
            sources=[{k:c[k] for k in ('source','section','chunk_id')}],
            citations=[dict(chunk_id=c['chunk_id'], quote='Fact.')])
        update = patch(payload['question'], 'goal') if payload['task_memory']['goal'] is None else {'changes': []}
        if self.mode in ('abstain', 'bad_abstain'):
            grounded = abstention()
        if self.mode in ('bad_memory', 'bad_abstain'):
            update = patch('not in the user')
        if self.mode == 'bad_grounded':
            grounded['citations'][0]['quote'] = 'Invented'
        return LlmResult('completed', reply=json.dumps(dict(grounded=grounded, memory_update=update)))


@pytest.fixture
def chat(tmp_path):
    chunks = [dict(chunk_id=str(i), source='doc.md', section='section', ordinal=i,
                   start_line=1, end_line=1, text='Fact.',
                   embedding=[1.0, float(i)/10]+[0.0]*(DIMENSION-2)) for i in range(5)]
    index = Index({'run_id':'test'}, chunks, [vector_norm(c['embedding']) for c in chunks], {'doc.md'})
    store = Day25Store(tmp_path/'chat.db')
    client, embedder = FakeClient(), FakeEmbedder()
    service = Day25ChatService(store, client, embedder, index)
    yield service, client, embedder
    store.close()


def patch(text, field='constraints', item_id=None, action='set'):
    return {'changes': [dict(field=field, action=action, item_id=item_id, quote=text)]}


def test_memory_provenance_correction_remove_and_noop():
    empty = TaskMemory().model_dump()
    first = reduce_memory(empty, patch('Same session'), '🧠 Same session.', 1)
    item = first['constraints'][0]
    assert item['source_start'] == 2 and item['source_end'] == 14
    assert reduce_memory(first, patch('Same session'), 'Same session', 2) == first
    changed = reduce_memory(first, patch('New session', item_id=item['id']), 'New session', 2)
    assert changed['constraints'][0]['source_user_turn'] == 2
    assert changed['constraints'][0]['id'] == item['id']
    assert reduce_memory(changed, patch('Cancel', item_id=item['id'], action='remove'), 'Cancel', 3) == empty


@pytest.mark.parametrize('proposal,current', [
    (patch('assistant-only'), 'Question?'),
    (patch('fact', item_id='unknown'), 'fact'),
    (patch('fact', action='remove'), 'fact'),
    (patch('x' * 257), 'x' * 257),
    ({'changes': patch('fact')['changes'] * 2}, 'fact'),
    ({'changes': [{**patch('fact')['changes'][0], 'source_user_turn': 1}]}, 'fact'),
])
def test_invalid_patch_never_mutates(proposal, current):
    before = TaskMemory().model_dump()
    with pytest.raises(ValueError):
        reduce_memory(before, proposal, current, 1)
    assert before == TaskMemory().model_dump()


def test_memory_limits_and_goal_target():
    changes = [patch(str(i))['changes'][0] for i in range(7)]
    with pytest.raises(ValueError):
        reduce_memory(TaskMemory().model_dump(), {'changes': changes}, '0123456', 1)
    first = reduce_memory(TaskMemory().model_dump(), patch('Goal', 'goal'), 'Goal', 1)
    with pytest.raises(ValueError):
        reduce_memory(first, patch('Other', 'goal'), 'Other', 2)


def test_store_atomic_reopen_delete_and_stale(tmp_path):
    path = tmp_path / 'chat.db'
    store = Day25Store(path)
    first, other = store.create(), store.create()
    sid = first['session_id']
    confirmed = store.commit_turn(sid, 0, 'Question', abstention(), first['memory'],
                                  'skipped_runtime_gate', str(uuid4()))
    with pytest.raises(ChatError, match='stale_revision'):
        store.commit_turn(sid, 0, 'Question', abstention(), first['memory'],
                          'skipped_runtime_gate', str(uuid4()))
    store.raw._db().execute("CREATE TRIGGER fail_memory BEFORE UPDATE ON chat_state BEGIN SELECT RAISE(ABORT, 'fault'); END")
    with pytest.raises(ConversationStorageError):
        store.commit_turn(sid, 1, 'Other', abstention(), first['memory'],
                          'skipped_runtime_gate', str(uuid4()))
    assert store.read(sid) == confirmed
    store.close()
    store = Day25Store(path)
    assert store.read(sid) == confirmed
    assert store.read(other['session_id']) == other
    store.delete(sid)
    store.delete(sid)
    with pytest.raises(ChatError, match='session_not_found'):
        store.read(sid)
    store.close()


def test_corrupt_memory_cannot_restore(tmp_path):
    store = Day25Store(tmp_path / 'chat.db')
    state = store.create()
    memory = reduce_memory(state['memory'], patch('invented'), 'invented', 1)
    store.raw._db().execute('UPDATE chat_state SET memory=?', (json.dumps(memory),))
    with pytest.raises(ConversationStorageError):
        store.read(state['session_id'])
    store.close()


@pytest.mark.asyncio
async def test_six_turn_window_actual_query_and_independent_context(chat):
    service, client, embedder = chat
    state = service.create()
    sid = state['session_id']
    records = []
    for n in range(6):
        result = await service.send(sid, 'early goal' if n == 0 else f'question {n+1}', n,
                                    observe=lambda x: records.append(x))
        assert result['response']['committed']
    observed = result['observation']
    assert len(service.read(sid)['history']) == 12
    assert [m['position'] for m in client.calls[-1]['recent_history']] == list(range(4, 10))
    assert [m['position'] for m in observed['before']['history']] == list(range(10))
    assert client.calls[-1]['task_memory']['goal']['source_user_turn'] == 1
    assert 'GOAL: early goal' in embedder.calls[-1][0]
    assert 'GOAL:' not in embedder.calls[0][0]
    assert len(embedder.calls) == len(client.calls) == 6
    assert set(client.calls[-1]) == {'question','recent_history','task_memory','rag_context'}
    assert len(client.calls[-1]['rag_context']) == 5
    raw_index = next(i for i, r in enumerate(records) if 'outcome' in r['generation'])
    assert records[raw_index]['grounded_validation']['status'] == 'not_run'


@pytest.mark.asyncio
@pytest.mark.parametrize('mode,gv,mv', [('bad_memory','passed','validation_failed'),
    ('bad_grounded','validation_failed','passed'),('bad_abstain','passed','validation_failed')])
async def test_independent_invalid_payloads_do_not_commit(chat, mode, gv, mv):
    service, client, embedder = chat
    client.mode = mode
    state = service.create()
    result = await service.send(state['session_id'], 'goal', 0)
    assert result['observation']['grounded_validation']['status'] == gv
    assert result['observation']['memory_validation']['status'] == mv
    assert result['response']['status'] == 'validation_failed'
    assert not result['response']['committed']
    assert service.read(state['session_id']) == state
    assert len(embedder.calls) == len(client.calls) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize('mode', ['gate', 'abstain'])
async def test_abstention_commits_pair_but_not_memory(chat, mode):
    service, client, embedder = chat
    client.mode = 'abstain'
    embedder.score_pass = mode != 'gate'
    state = service.create()
    result = await service.send(state['session_id'], 'critical early goal', 0)
    assert result['response']['grounded'] == abstention()
    after = service.read(state['session_id'])
    assert after['memory'] == state['memory'] and after['revision'] == 1
    assert len(client.calls) == (0 if mode == 'gate' else 1)


@pytest.mark.asyncio
@pytest.mark.parametrize('mode', ['refused', 'incomplete', 'error'])
async def test_provider_failure_is_not_turn(chat, mode):
    service, client, embedder = chat
    client.mode = mode
    state = service.create()
    result = await service.send(state['session_id'], 'goal', 0)
    assert not result['response']['committed'] and service.read(state['session_id']) == state
    assert len(client.calls) == len(embedder.calls) == 1


@pytest.mark.asyncio
async def test_busy_stale_cancellation_and_bad_index(chat):
    service, client, embedder = chat
    state = service.create()
    sid = state['session_id']
    with pytest.raises(ChatError, match='stale_revision'):
        await service.send(sid, 'goal', 1)
    with service.claim(sid):
        with pytest.raises(ChatError, match='session_busy'):
            await service.send(sid, 'goal', 0)
        with pytest.raises(ChatError, match='session_busy'):
            service.delete(sid)
    class Cancelled:
        async def complete(self, messages, config):
            raise asyncio.CancelledError
    service.client = Cancelled()
    with pytest.raises(asyncio.CancelledError):
        await service.send(sid, 'goal', 0)
    assert service.read(sid) == state and not service.busy
    service.index.chunks[0]['embedding'] = [0.0]
    result = await service.send(sid, 'goal', 0)
    assert result['response']['status'] == 'error'
    assert service.read(sid) == state


@pytest.mark.asyncio
async def test_api_contract(chat):
    from fastapi import FastAPI
    import httpx
    from app.stateful_rag.api import router
    app = FastAPI()
    app.state.day25_chat = chat[0]
    app.include_router(router)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as api:
        root = '/api/v1/day25/sessions'
        assert (await api.post(root, json={'history': []})).status_code == 422
        created = await api.post(root, json={})
        assert created.status_code == 201
        sid = created.json()['session_id']
        path = f'{root}/{sid}'
        assert (await api.get(path)).json() == created.json()
        assert (await api.post(path+'/messages', json={'message':'x', 'expected_revision':1})).status_code == 409
        sent = await api.post(path+'/messages', json={'message':'goal', 'expected_revision':0})
        assert sent.status_code == 200 and sent.json()['status'] == 'accepted'
        assert sent.json()['state']['revision'] == 1
        for _ in range(2):
            assert (await api.delete(path)).status_code == 204
        assert (await api.get(path)).status_code == 404
        assert (await api.post(path+'/messages', json={'message':'x','expected_revision':0})).status_code == 404


@pytest.mark.asyncio
@pytest.mark.parametrize('stage', ['embedding', 'generation', 'raw', 'commit', 'after'])
async def test_evidence_failure_stops_dispatch_and_never_invents_rollback(chat, stage):
    from app.stateful_rag.service import EvidenceError
    service, client, embedder = chat
    state = service.create()
    def observer(r):
        actual = ('after' if r['commit_status'] == 'committed' else
                  'commit' if r['commit_status'] == 'unknown' else
                  'raw' if 'outcome' in r['generation'] else
                  'generation' if r['generation']['attempted'] else 'embedding')
        if actual == stage:
            raise OSError('disk failure')
    with pytest.raises(EvidenceError):
        await service.send(state['session_id'], 'goal', 0, observe=observer)
    assert len(embedder.calls) == (0 if stage == 'embedding' else 1)
    assert len(client.calls) == (0 if stage in ('embedding','generation') else 1)
    assert service.read(state['session_id'])['revision'] == (1 if stage == 'after' else 0)
