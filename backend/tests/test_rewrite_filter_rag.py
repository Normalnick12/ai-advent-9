import asyncio
from dataclasses import asdict
import json
import os
from pathlib import Path
import runpy
import subprocess
import sys

import pytest

from app.first_rag.core import Index, search, vector_norm
from app.document_indexing.embedding import DIMENSION
from app.document_indexing.corpus import ROOT, canonical, digest
from app.first_rag import core as baseline_core
from app.first_rag.experiment import read_json, write_json, review_template as baseline_review
from app.llm_client import LlmResult, TokenUsage
from app.openai_agent_payload import generation_payload
from app.rewrite_filter_rag import core, experiment


def vector(x=1, y=0):
    return [x, y] + [0.0] * (DIMENSION - 2)


@pytest.fixture
def index():
    chunks = [dict(chunk_id=str(i), source=f"doc{i:02}.md", section=f"Section {i}",
                   ordinal=0, start_line=1, end_line=2, text=f"Full chunk {i}\nData.",
                   embedding=vector(12-i, i)) for i in range(12)]
    return Index({}, chunks, [vector_norm(c['embedding']) for c in chunks], set())


def test_search_default_and_top10(index):
    five, ten = search(index, vector()), search(index, vector(), top_k=10)
    assert len(five) == 5 and len(ten) == 10 and five == ten[:5]
    index.chunks[1]['embedding'] = vector()
    index.norms[1] = 1
    assert [c['chunk_id'] for c in search(index, vector(), top_k=10)][:2] == ['0', '1']
    assert all(c['score'] < 0 for c in search(index, vector(-1), top_k=10))
    for bad in (0, True, 13, 1.5):
        with pytest.raises(ValueError):
            search(index, vector(), top_k=bad)


class Client:
    def __init__(self, outcome=None):
        self.calls = []
        self.outcome = outcome or LlmResult('completed', reply='  exact retrieval query\n',
                                           usage=TokenUsage(input_tokens=20, output_tokens=5))

    async def complete(self, messages, config):
        self.calls.append((messages, config))
        return self.outcome


class Embedder:
    def __init__(self, value=None, fail=False):
        self.calls = []
        self.value = vector() if value is None else value
        self.fail = fail

    def embed(self, texts):
        from app.document_indexing.embedding import Embeddings
        self.calls.append(texts)
        if self.fail:
            raise ValueError('secret upstream body')
        return Embeddings([self.value], 6)


@pytest.fixture
def baseline(tmp_path, index):
    frozen = read_json(baseline_core.QUESTIONS)
    index.sources = {s for q in frozen['questions'] for s in q['acceptable_sources']}
    index.provenance = dict(run_id=baseline_core.RUN_ID, corpus_hash=baseline_core.CORPUS_HASH,
                            strategy=baseline_core.STRATEGY, chunk_count=226)
    folder = tmp_path/'baseline'
    folder.mkdir()
    run = dict(eval_id=core.BASELINE_ID, command='eval', index=index.provenance,
               config=asdict(baseline_core.CONFIG), question_hash=digest(canonical(frozen)),
               frozen_question_set=frozen, questions=frozen['questions'])
    write_json(folder/'run.json', run)
    write_json(folder/'review.json', baseline_review(run))
    for q in frozen['questions']:
        hits = search(index, vector())
        write_json(folder/f"{q['id']}.json", dict(id=q['id'], question=q['question'],
            retrieval=dict(status='completed', hits=hits, usage=6),
            direct=dict(status='completed', attempted=True, config=run['config'],
                        outcome={'reply':'saved direct'}, usage=None),
            rag=dict(status='completed', attempted=True, config=run['config'],
                     outcome={'reply':'saved baseline'}, usage=None)))
    return folder, core.load_baseline(folder, index)


def saved(tmp_path, baseline, index, **kwargs):
    return asyncio.run(experiment.retrieve(baseline[1], index, output_root=tmp_path/'results',
        client=kwargs.get('client') or Client(), embedder=kwargs.get('embedder') or Embedder(),
        progress=lambda _: None))


@pytest.mark.parametrize('field', ['eval_id','question_hash','config','index'])
def test_baseline_mismatch_before_calls(baseline,index,field):
    folder,_ = baseline
    run = read_json(folder/'run.json')
    run[field] = 'wrong'
    write_json(folder/'run.json',run)
    with pytest.raises((ValueError,KeyError,TypeError)):
        core.load_baseline(folder,index)


def test_filter_boundary_k_limit_and_empty():
    candidates=[{'rank':i+1,'score':s,'chunk_id':str(i)} for i,s in enumerate(
        [.9,.8,.7,.6,.55,.51,.50,.49,.4,.1])]
    decisions,kept=core.select(candidates)
    assert kept==candidates[:5]
    assert [c['decision'] for c in decisions]==['kept']*5+['dropped_top_k_limit']*2+['dropped_below_threshold']*3
    assert core.select([{'score':.50}])[1]==[{'score':.50}]
    assert core.select([{'score':.49999}])[1]==[]


def test_chain_inputs_calls_and_immutable_baseline(tmp_path,baseline,index):
    client,embedder=Client(),Embedder()
    before={p.name:p.read_bytes() for p in baseline[0].glob('*.json')}
    folder=saved(tmp_path,baseline,index,client=client,embedder=embedder)
    run,b,review,records=experiment.load_saved(folder)
    assert len(client.calls)==len(embedder.calls)==10
    assert embedder.calls==[['  exact retrieval query\n']]*10
    for q,(msgs,cfg) in zip(run['questions'],client.calls):
        assert msgs[0].content==q['question'] and len(msgs)==1
        assert cfg==core.REWRITE_CONFIG
        r=records[q['id']]
        assert r['rewrite']['request']==generation_payload(msgs,cfg)
        assert r['retrieval_query']=='  exact retrieval query\n'
        assert len(r['retrieval']['candidates'])==10
        assert r['enhanced']['attempted'] is False
        assert review['questions'][q['id']]['rewrite_preserves_intent'] is None
    generation_client=Client(LlmResult('completed',reply='saved enhanced'))
    asyncio.run(experiment.compare(folder,client=generation_client,progress=lambda _:None))
    assert len(generation_client.calls)==10 and len(embedder.calls)==10 and len(client.calls)==10
    for q,(msgs,cfg) in zip(run['questions'],generation_client.calls):
        payload=json.loads(msgs[0].content)
        assert payload['question']==q['question']
        assert set(payload)=={'question','context'} and cfg==baseline_core.CONFIG
        kept=records[q['id']]['retrieval']['final_context']
        assert [c['text'] for c in payload['context']]==[c['text'] for c in kept]
        assert [c['label'] for c in payload['context']]==[f'[S{i}]' for i in range(1,len(kept)+1)]
    with pytest.raises(ValueError,match='already attempted'):
        asyncio.run(experiment.compare(folder,client=generation_client))
    assert len(generation_client.calls)==10
    assert before=={p.name:p.read_bytes() for p in baseline[0].glob('*.json')}


@pytest.mark.parametrize('outcome', [LlmResult('incomplete'),LlmResult('refused'),
    LlmResult('error',error_code='llm_timeout'), LlmResult('completed',reply='  ')])
def test_bad_rewrite_does_not_fallback(tmp_path,baseline,index,outcome):
    client,embedder=Client(outcome),Embedder()
    folder=saved(tmp_path,baseline,index,client=client,embedder=embedder)
    assert len(client.calls)==10 and embedder.calls==[]
    gen=Client()
    asyncio.run(experiment.compare(folder,client=gen,progress=lambda _:None))
    assert gen.calls==[]
    assert read_json(folder/'Q01.json')['enhanced']['reason']=='retrieval_unavailable'


@pytest.mark.parametrize('embedder',[Embedder(fail=True),Embedder(value=[0.0]*DIMENSION)])
def test_bad_embedding_is_unavailable(tmp_path,baseline,index,embedder):
    folder=saved(tmp_path,baseline,index,embedder=embedder)
    gen=Client()
    asyncio.run(experiment.compare(folder,client=gen,progress=lambda _:None))
    assert gen.calls==[] and len(embedder.calls)==10
    assert 'secret upstream body' not in (folder/'Q01.json').read_text(encoding='utf-8')


def test_empty_context_is_success(tmp_path,baseline,index):
    folder=saved(tmp_path,baseline,index,embedder=Embedder(vector(-1)))
    gen=Client(LlmResult('incomplete',incomplete_reason='max_output_tokens'))
    asyncio.run(experiment.compare(folder,client=gen,progress=lambda _:None))
    assert len(gen.calls)==10
    assert all(json.loads(m[0].content)['context']==[] for m,cfg in gen.calls)
    r=read_json(folder/'Q10.json')
    assert r['retrieval']['status']=='completed' and r['retrieval']['final_context']==[]
    assert r['enhanced']['status']=='incomplete'


def test_changed_retrieval_stops_compare(tmp_path,baseline,index):
    folder=saved(tmp_path,baseline,index)
    r=read_json(folder/'Q01.json');r['retrieval_query']='edited'
    write_json(folder/'Q01.json',r)
    gen=Client()
    with pytest.raises(ValueError,match='retrieval changed'):
        asyncio.run(experiment.compare(folder,client=gen))
    assert gen.calls==[]


def test_storage_failure_before_dispatch(tmp_path,baseline,index,monkeypatch):
    client,embedder=Client(),Embedder()
    def fail(*args):raise OSError('storage unavailable')
    monkeypatch.setattr(experiment,'write_json',fail)
    with pytest.raises(OSError):saved(tmp_path,baseline,index,client=client,embedder=embedder)
    assert client.calls==[] and embedder.calls==[]


def test_storage_failure_after_rewrite_stops_calls(tmp_path,baseline,index,monkeypatch):
    original=experiment.write_json
    client,embedder=Client(),Embedder()
    def fail(path,value):
        if Path(path).name=='Q01.json' and value['rewrite'].get('outcome'):
            raise OSError('disk unavailable')
        original(path,value)
    monkeypatch.setattr(experiment,'write_json',fail)
    with pytest.raises(OSError):saved(tmp_path,baseline,index,client=client,embedder=embedder)
    assert len(client.calls)==1 and embedder.calls==[]
    r=read_json(next((tmp_path/'results').glob('*/Q01.json')))
    assert r['rewrite']['status']=='unknown'


def test_unexpected_interruption_stays_unknown(tmp_path,baseline,index):
    class Interrupted(Client):
        async def complete(self,*args):raise RuntimeError('interrupted')
    with pytest.raises(RuntimeError):saved(tmp_path,baseline,index,client=Interrupted())
    r=read_json(next((tmp_path/'results').glob('*/Q01.json')))
    assert r['rewrite']['status']=='unknown' and r['embedding']['attempted'] is False


def test_manual_review_and_keyless_offline_report(tmp_path,baseline,index):
    from app.rewrite_filter_rag.report import render
    folder=saved(tmp_path,baseline,index)
    asyncio.run(experiment.compare(folder,client=Client(),progress=lambda _:None))
    review=read_json(folder/'review.json')
    item=review['questions']['Q01']
    assert item['rewrite_preserves_intent'] is None and item['rewrite_added_project_assumption'] is None
    item.update(status='reviewed',rewrite_preserves_intent='partial',rewrite_added_project_assumption='yes')
    item['facts']['F1'].update(expected_fact_in_retrieved_context='partial',enhanced_answer_covers_fact='no')
    item['claims']=[{'claim':'unsupported fixture','grounded_in_retrieved_context':'no'}]
    write_json(folder/'review.json',review)
    assert 'rewrite_preserves_intent: partial' in render(folder,question_id='Q01')
    assert 'pending / partial / pending / no' in render(folder,question_id='Q01')
    before={p.name:p.read_bytes() for p in folder.glob('*.json')}
    baseline[0].rename(tmp_path/'original-baseline-unavailable')
    env={k:v for k,v in os.environ.items() if k!='OPENAI_API_KEY'}
    result=subprocess.run([sys.executable,str(ROOT/'backend/scripts/day23_rag.py'),'report',str(folder),
                           '--question','Q01','--full'],env=env,capture_output=True,text=True,
                          encoding='utf-8',check=True)
    markers=['ORIGINAL QUESTION','RETRIEVAL QUERY','TOP-10 BEFORE','THRESHOLD 0.50',
             'FINAL CONTEXT','DAY 22 BASELINE ANSWER','DAY 23 ENHANCED ANSWER','EXPECTED FACTS / REVIEW']
    assert [result.stdout.index(m) for m in markers]==sorted(result.stdout.index(m) for m in markers)
    assert 'Full chunk' in result.stdout and 'Grounded=no' in result.stdout
    assert before=={p.name:p.read_bytes() for p in folder.glob('*.json')}
    assert 'context22 | context23 | answer22 | answer23' in render(folder)
    item['rewrite_preserves_intent']='invalid'
    write_json(folder/'review.json',review)
    with pytest.raises(ValueError,match='rewrite review'):
        render(folder)


def test_video_cli_is_read_only_and_preserves_detailed_report(tmp_path,baseline,index,monkeypatch,capsys):
    from app.first_rag.client import ObservedClient
    from app.document_indexing.embedding import OpenAIEmbedder
    from app.rewrite_filter_rag.report import render

    folder=saved(tmp_path,baseline,index)
    asyncio.run(experiment.compare(folder,client=Client(),progress=lambda _:None))
    before={p.name:p.read_bytes() for p in folder.iterdir()}
    detailed=render(folder,question_id='Q01',full=True)

    def forbidden(*args,**kwargs):
        pytest.fail('Offline report must never dispatch provider calls')

    monkeypatch.delenv('OPENAI_API_KEY',raising=False)
    monkeypatch.setattr(ObservedClient,'__init__',forbidden)
    monkeypatch.setattr(OpenAIEmbedder,'__init__',forbidden)
    cli=runpy.run_path(str(ROOT/'backend/scripts/day23_rag.py'),run_name='day23_report_test')
    for flags in (['--question','Q01','--full'], ['--video'], ['--question','Q01','--video']):
        args=cli['parser']().parse_args(['report',str(folder),*flags])
        asyncio.run(cli['execute'](args))
        output=capsys.readouterr().out
        if '--video' not in flags:
            assert output==detailed+'\n'
        elif '--question' not in flags:
            assert all(m in output for m in ('SAVED RUN','PIPELINE','PROVIDER CALLS / STATUS','RESULT'))
        else:
            markers=['1. QUESTION','2. REWRITE','3. IMPORTANT CANDIDATES','4. FINAL CONTEXT',
                     '5. BASELINE vs ENHANCED FACT COVERAGE','6. BASELINE vs ENHANCED ANSWER COVERAGE','7. TAKEAWAY']
            assert [output.index(m) for m in markers]==sorted(output.index(m) for m in markers)
    assert before=={p.name:p.read_bytes() for p in folder.iterdir()}
