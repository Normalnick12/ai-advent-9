from copy import deepcopy
from unittest.mock import AsyncMock

import pytest

from app import main
from app.personalization_models import *
from app.profiles import ProfileError
from test_personalization import lab, prepare, refs, probe_request, setup_profiles


@pytest.mark.asyncio
async def test_lifespan_paths_are_isolated_and_all_resources_close(tmp_path, monkeypatch):
    paths = ['agent_database_path','token_database_path','compression_database_path','strategies_database_path',
             'memory_database_path','personalization_memory_path','profile_database_path']
    for key in paths:
        monkeypatch.setattr(main.app.state,key,tmp_path / (key+'.db'))
    clients=[]
    def client():
        c=AsyncMock(); clients.append(c); return c
    monkeypatch.setattr(main,'OpenAIResponsesLlmClient',client)
    monkeypatch.setattr(main,'OpenAIInputTokenCounter',client)
    async with main.app.router.lifespan_context(main.app):
        svc=main.app.state.personalization
        assert svc.current()['memory'] is None
        assert main.app.state.memory_layers.read()['state'] is None
        setup_profiles(svc)
        assert main.app.state.memory_layers.read()['state'] is None
    assert all(c.close.await_count==1 and c.complete.await_count==0 for c in clients)
    async with main.app.router.lifespan_context(main.app):
        restored=main.app.state.personalization.current()
        assert restored['preparation']=='ready' and restored['generation_calls']==0
        assert restored['memory']['short_term']==[]
    monkeypatch.setattr(main.app.state,'profile_database_path',main.app.state.memory_database_path)
    with pytest.raises(ValueError,match='different database'):
        async with main.app.router.lifespan_context(main.app):
            pytest.fail('path collision accepted')


@pytest.mark.asyncio
async def test_freeze_preconditions_stale_revision_and_profile_edit(lab):
    svc,client=lab
    pair=setup_profiles(svc)
    frozen=lambda: FreezeRequest(**refs(svc),profile_a_id=pair['A']['profile_id'],profile_a_revision=0,
        profile_b_id=pair['B']['profile_id'],profile_b_revision=0)
    with pytest.raises(ProfileError,match='comparison_setup_required'):
        svc.freeze(frozen())
    assert not client.calls and svc.comparison is None
    # A custom edit changes behavior while preserving memory/binding; not silently overwritten by fixtures.
    before=deepcopy(svc.current())
    edited=svc.edit(pair['A']['profile_id'],EditProfile(owner_id=svc.owner(),expected_revision=0,
        fields=FIXTURES['A'].model_copy(update={'verbosity':'detailed'})))
    assert edited['current']['memory']==before['memory'] and edited['current']['binding']==before['binding']
    with pytest.raises(ProfileError,match='stale_profile'):
        svc.edit(pair['A']['profile_id'],EditProfile(owner_id=svc.owner(),expected_revision=0,fields=FIXTURES['A']))
    from app.llm_client import LlmResult
    client.result=LlmResult('error',error_code='failed_seed')
    result=await svc.send(RequestSnapshot(**refs(svc)),seed=True)
    assert not result['observation']['committed'] and svc.current()['memory']==before['memory']
    assert len(client.calls)==1


@pytest.mark.asyncio
async def test_frozen_record_is_independent_of_mutable_views_and_stale_edits(lab):
    svc,client=lab
    pair=await prepare(svc)
    view=svc.current()
    view['memory']['working']['task']='other'
    view['comparison']['profiles']['A']['tone']='explanatory'
    result=await svc.probe(probe_request(svc,'A'))
    result['observation']['memory']['working']['task']='changed receipt'
    assert svc.current()['memory']['working']['task']=='Checkout'
    assert svc.current()['comparison']['profiles']['A']['tone']=='technical'
    svc.edit(pair['B']['profile_id'],EditProfile(owner_id=svc.owner(),expected_revision=0,
        fields=FIXTURES['B'].model_copy(update={'name':'Renamed only'})))
    assert not svc.current()['comparison']['valid']
    with pytest.raises(ProfileError,match='stale_comparison'):
        await svc.probe(probe_request(svc,'A'))
    assert len(client.calls)==2
