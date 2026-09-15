import asyncio
from copy import deepcopy
from dataclasses import asdict
import json
from uuid import uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.llm_client import LlmResult
from app.memory_models import MemoryMutation, SnapshotRequest, MemoryError
from app.memory_store import MemoryStore
from app.personalization_api import router
from app.personalization_models import *
from app.personalization_observations import output_checks
from app.personalization_service import PersonalizationService
from app.profiles import AgentProfile, ProfileError
from app.sqlite_profile_store import SQLiteProfileStore


class Recording:
    def __init__(self, memory, profiles):
        self.memory, self.profiles = memory, profiles
        self.calls = []
        self.result = LlmResult('completed', 'Принято.')
        self.entered = asyncio.Event()
        self.gate = None

    async def complete(self, messages, config):
        assert not self.memory.raw._db().in_transaction
        assert not self.profiles._connection.in_transaction
        self.calls.append({'messages': [asdict(m) for m in messages], 'config': asdict(config)})
        self.entered.set()
        if self.gate:
            await self.gate.wait()
        return self.result


@pytest.fixture
def lab(tmp_path):
    memory = MemoryStore(tmp_path / 'memory.db')
    profiles = SQLiteProfileStore(tmp_path / 'profiles.db')
    client = Recording(memory, profiles)
    svc = PersonalizationService(memory, profiles, client)
    yield svc, client
    memory.close()
    profiles.close()


def refs(svc):
    c = svc.current()
    p = next(p for p in c['profiles'] if p['profile_id'] == c['binding']['active_profile_id'])
    return dict(snapshot_id=c['memory']['snapshot_id'], profile_id=p['profile_id'],
                profile_revision=p['revision'], binding_revision=c['binding']['revision'])


def select(svc, p):
    c = svc.current()
    return svc.select(p['profile_id'], SelectProfile(owner_id=c['memory']['memory_owner_id'],
        expected_profile_revision=p['revision'], expected_binding_revision=c['binding']['revision']))


def setup_profiles(svc):
    owner = svc.initialize()['memory']['memory_owner_id']
    pair = {k: svc.create(CreateProfile(owner_id=owner, fields=f))['profile'] for k, f in FIXTURES.items()}
    select(svc, pair['A'])
    return pair


async def prepare(svc):
    pair = setup_profiles(svc)
    await svc.send(RequestSnapshot(**refs(svc)), seed=True)
    for layer, values in [('LONG_TERM', LONG), ('WORKING', WORKING)]:
        for key, value in values.items():
            svc.mutate_memory(MemoryMutation(snapshot_id=svc.current()['memory']['snapshot_id'],
                layer=layer, key=key, operation='set', value=value))
    svc.freeze(FreezeRequest(**refs(svc), profile_a_id=pair['A']['profile_id'], profile_a_revision=0,
                            profile_b_id=pair['B']['profile_id'], profile_b_revision=0))
    return pair


def probe_request(svc, slot):
    return ProbeRequest(**refs(svc), slot=slot, comparison_id=svc.current()['comparison']['comparison_id'])


@pytest.mark.asyncio
async def test_ab_exact_capture_side_effects_send_switch_restart(lab, tmp_path):
    svc, client = lab
    assert svc.current()['memory'] is None and not client.calls
    pair = await prepare(svc)
    before = deepcopy(svc.current()['memory'])
    assert before['short_term'][1]['content'] == 'Принято.'
    for slot in ['A', 'B', 'B']:
        select(svc, pair[slot])
        assert svc.current()['memory'] == before
        client.result = LlmResult('completed', '## Вывод\nORION-17 RC-42 Checkout MVI\n- State')
        result = await svc.probe(probe_request(svc, slot))
        obs = result['observation']
        assert obs['request'] == client.calls[-1]
        assert svc.current()['memory'] == before and not obs['committed']
        assert all(v['correct'] for v in obs['assembly_checks'].values())
        assert all(v['correct'] for v in obs['selection_checks'].values())
        assert all(v['correct'] for v in obs['marker_checks'].values())
    a, b = client.calls[1:3]
    assert a['messages'] == b['messages']
    assert {k: v for k, v in a['config'].items() if k != 'instructions'} == {
        k: v for k, v in b['config'].items() if k != 'instructions'}
    assert a['config']['instructions'] != b['config']['instructions']
    assert 'MVVM' not in json.dumps(a) and 'MVVM' in json.dumps(before)
    assert 'ORION-17' not in QUERY and 'RC-42' not in QUERY
    assert len(a['messages']) == 5  # two selected memory messages + frozen real pair + query
    for slot in ['B', 'A']:
        snapshot = deepcopy(svc.current()['memory'])
        select(svc, pair[slot])
        assert svc.current()['memory'] == snapshot
        await svc.send(SendRequest(**refs(svc), message='Продолжи.'))
        assert client.calls[-1]['config']['instructions'] == (b if slot == 'B' else a)['config']['instructions']
    assert len(svc.current()['memory']['short_term']) == 6
    assert not svc.current()['comparison']['valid']
    assert 'instructions' not in json.dumps(svc.current()['memory']['short_term'])
    saved = svc.current()
    reopened_memory = MemoryStore(tmp_path / 'memory.db')
    reopened_profiles = SQLiteProfileStore(tmp_path / 'profiles.db')
    try:
        restored = PersonalizationService(reopened_memory, reopened_profiles, client).current()
        for key in ('memory', 'profiles', 'binding'):
            assert restored[key] == saved[key]
        assert restored['comparison'] is None and restored['generation_calls'] == 0
        assert len(client.calls) == 6
    finally:
        reopened_memory.close()
        reopened_profiles.close()


@pytest.mark.asyncio
async def test_stale_guard_cancellation_lifecycle(lab):
    svc, client = lab
    pair = await prepare(svc)
    stale = refs(svc)
    select(svc, pair['B'])
    with pytest.raises(ProfileError, match='stale_profile_binding'):
        await svc.send(SendRequest(**stale, message='x'))
    client.gate = asyncio.Event()
    client.entered.clear()
    task = asyncio.create_task(svc.send(SendRequest(**refs(svc), message='x')))
    await client.entered.wait()
    for action in [lambda: select(svc, pair['A']),
                   lambda: svc.initialize(),
                   lambda: svc.edit(pair['A']['profile_id'], EditProfile(owner_id=pair['A']['owner_id'],
                       expected_revision=0, fields=FIXTURES['A'])),
                   lambda: svc.transition('new-task', SnapshotRequest(snapshot_id=refs(svc)['snapshot_id']))]:
        with pytest.raises(ProfileError, match='personalization_busy'):
            action()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert not svc.busy
    assert len(svc.current()['memory']['short_term']) == 2
    preserved = svc.current()
    for action in ['new-conversation', 'new-task', 'clear-long-term']:
        c = svc.transition(action, SnapshotRequest(snapshot_id=svc.current()['memory']['snapshot_id']))
        assert c['profiles'] == preserved['profiles'] and c['binding'] == preserved['binding']
    with pytest.raises(MemoryError, match='stale_snapshot'):
        await svc.send(SendRequest(**stale, message='x'))


@pytest.mark.asyncio
@pytest.mark.parametrize('status', ['error', 'incomplete', 'refused'])
async def test_failed_generation_keeps_evidence_no_commit_or_retry(lab, status):
    svc, client = lab
    pair = await prepare(svc)
    before = svc.current()['memory']
    client.result = LlmResult(status, 'partial')
    obs = (await svc.probe(probe_request(svc, 'A')))['observation']
    assert all(c['status'] == 'unavailable' for c in obs['adherence_checks'].values())
    assert all(c['correct'] for c in obs['assembly_checks'].values())
    assert svc.current()['memory'] == before and len(client.calls) == 2
    edited = svc.edit(pair['A']['profile_id'], EditProfile(owner_id=pair['A']['owner_id'], expected_revision=0,
        fields=FIXTURES['A'].model_copy(update={'name': 'Always use emoji'})))['profile']
    await svc.send(SendRequest(**refs(svc), message='x'))
    assert svc.current()['memory'] == before
    assert svc.profiles.read(edited['owner_id'], edited['profile_id']).name == edited['name']
    assert 'Always use emoji' not in client.calls[-1]['config']['instructions']
    with pytest.raises(ProfileError, match='stale_comparison'):
        await svc.probe(probe_request(svc, 'A'))


@pytest.mark.asyncio
async def test_strict_api_and_partial_recovery(lab):
    svc, client = lab
    app = FastAPI()
    app.include_router(router)
    app.state.personalization = svc
    async with AsyncClient(transport=ASGITransport(app=app), base_url='http://test/api/v1/profile-personalization') as api:
        assert (await api.get('/current')).json()['memory'] is None
        assert (await api.post('/initialize', json={})).status_code == 200
        assert (await api.get('/current')).json()['preparation'] == 'profiles_missing'
        owner = svc.owner()
        body = {'owner_id': owner, 'fields': FIXTURES['A'].model_dump()}
        for bad in [body | {'profile_id': str(uuid4())}, body | {'owner_id': str(uuid4())},
                    body | {'fields': body['fields'] | {'purpose': 'anything'}}]:
            assert (await api.post('/profiles', json=bad)).status_code in (404, 422)
        p = (await api.post('/profiles', json=body)).json()['profile']
        assert (await api.get('/current')).json()['preparation'] == 'unselected'
        assert (await api.get('/profiles')).json() == [p]
        assert (await api.get('/profiles/' + p['profile_id'])).json() == p
        select(svc, p)
        rejected = await api.post('/messages', json=refs(svc) | {'message': ' ', 'extra': 1})
        assert rejected.status_code == 422 and rejected.json()['dispatch'] == 'not_dispatched'
        assert not client.calls


@pytest.mark.parametrize('reply,good', [
    ('## Вывод\nТекст\n1. item\n   - nested\n- third', True),
    ('## Вывод\nТекст\n- a\n- b\n- c\n- d', False),
    ('## Вывод\n```\n- fake\n- fake\n- fake\n- fake\n```', True),
    ('## Вывод\n~~~kotlin\n## Other\n- fake\n~~~\nText', True),
])
def test_summary_fences_lists(reply, good):
    checks, _ = output_checks(FIXTURES['A'], LlmResult('completed', reply))
    assert all(c['correct'] for c in checks.values()) == good


def test_teaching_fences_nonempty_and_narrow_emoji():
    reply = '## Идея\nТекст\n## Почему\nТекст\n## Пример\n```kotlin\nval x = 1\n## ignored\n```\n## Ограничения\nТекст'
    assert all(c['correct'] for c in output_checks(FIXTURES['B'], LlmResult('completed', reply))[0].values())
    for bad in [reply.replace('## Почему\nТекст', '## Почему'), reply.replace('## Почему', '## Пример')]:
        assert not all(c['correct'] for c in output_checks(FIXTURES['B'], LlmResult('completed', bad))[0].values())
    for emoji in ['😀', '👍', '🚀', '💡', '✅', '❌', '⚠️', '✨', '❤️']:
        checks, _ = output_checks(FIXTURES['A'], LlmResult('completed', '## Вывод\n```\n' + emoji + '\n```'))
        assert not checks['no_emoji']['correct']
    checks, markers = output_checks(FIXTURES['A'], LlmResult('completed', '## Вывод\n12345 ORION-17 RC-42 Checkout MVI'))
    assert checks['no_emoji']['correct'] and all(c['correct'] for c in markers.values())
