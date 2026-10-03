import asyncio
from copy import deepcopy
from dataclasses import asdict
import json
from pathlib import Path
import runpy

import pytest

from app.document_indexing.corpus import ROOT, canonical, digest
from app.document_indexing.embedding import DIMENSION, EMBEDDING_CONFIG
from app.first_rag import core as old
from app.first_rag.experiment import read_json, write_json, review_template as old_review
from app.grounded_rag import core
from app.grounded_rag import experiment, report
from app.llm_client import LlmResult
from app.openai_agent_payload import generation_payload
from app.rewrite_filter_rag.core import BASELINE_ID


@pytest.fixture
def baseline(tmp_path):
    frozen = read_json(old.QUESTIONS)
    chunks = [dict(chunk_id=str(i), source=f'doc{i}.md', section=f'Section {i}',
        ordinal=0, start_line=1, end_line=2, text=f'Fact {i}.\nExact  spacing é.',
        embedding=[1.0, float(i)] + [0.0] * (DIMENSION-2)) for i in range(5)]
    index = old.Index(dict(run_id=old.RUN_ID, corpus_hash=old.CORPUS_HASH,
        strategy=old.STRATEGY, chunk_count=226), chunks,
        [old.vector_norm(c['embedding']) for c in chunks],
        {s for q in frozen['questions'] for s in q['acceptable_sources']})
    folder = tmp_path/'baseline'
    folder.mkdir()
    run = dict(eval_id=BASELINE_ID, command='eval', index=index.provenance,
        config=asdict(old.CONFIG), question_hash=digest(canonical(frozen)),
        frozen_question_set=frozen, questions=frozen['questions'])
    write_json(folder/'run.json', run)
    write_json(folder/'review.json', old_review(run))
    for q in run['questions']:
        vector = [(-1.0 if q['id']=='Q10' else 1.0)] + [0.0]*(DIMENSION-1)
        write_json(folder/f"{q['id']}.json", dict(id=q['id'], question=q['question'],
            retrieval=dict(status='completed', input={'texts':[q['question']], **EMBEDDING_CONFIG},
                           query_vector=vector, hits=old.search(index,vector)),
            direct=dict(attempted=False), rag=dict(attempted=False)))
    return folder,index


def answer(context):
    c = context[0]
    return dict(status='answered', answer='Fact 0.',
        sources=[{k:c[k] for k in ('source','section','chunk_id')}],
        citations=[dict(chunk_id=c['chunk_id'],quote='Fact 0.')])


@pytest.fixture
def context(baseline):
    saved,retrieval = core.replay(*baseline)
    q = saved['run']['questions'][0]
    hits = retrieval[q['id']]['hits']
    request = generation_payload(core.messages(q['question'],hits),core.CONFIG)
    return core.context_from_request(request,q['question'],hits)


def test_replay_and_payload(baseline):
    folder,index = baseline
    before = {p.name:p.read_bytes() for p in folder.iterdir()}
    saved,rs = core.replay(folder,index)
    assert before == {p.name:p.read_bytes() for p in folder.iterdir()}
    assert len(rs)==10
    assert sum(core.gate(r['hits'])['decision']=='pass' for r in rs.values())==9
    q=saved['run']['questions'][0]
    hits=rs[q['id']]['hits']
    assert hits[-1]['score'] < .5
    payload=generation_payload(core.messages(q['question'],hits),core.CONFIG)
    context=core.context_from_request(payload,q['question'],hits)
    assert len(context)==5 and context[-1]['text']==hits[-1]['text']
    assert [c['chunk_id'] for c in context]==[c['chunk_id'] for c in hits]
    assert set(json.loads(payload['input'][0]['content']))=={'question','context'}
    assert all(set(c)=={'label','chunk_id','source','section','start_line','end_line','text'} for c in context)
    assert payload['max_output_tokens']==3000 and payload['store'] is False
    assert payload['model']=='gpt-5.6' and payload['truncation']=='disabled'
    assert payload['text']['format']['strict'] is True
    schema=payload['text']['format']['schema']
    for obj in [schema,*schema['$defs'].values()]:
        assert obj['additionalProperties'] is False
        assert set(obj['required'])==set(obj['properties'])
    payload['input'][0]['content']='{}'
    with pytest.raises(ValueError,match='Actual request'):
        core.context_from_request(payload,q['question'],hits)


@pytest.mark.parametrize('bad', ['question','config','status','vector','hits','missing'])
def test_replay_rejects_corruption(baseline,bad):
    folder,index=baseline
    path=folder/'Q10.json'
    record=read_json(path)
    r=record['retrieval']
    if bad=='question': r['input']['texts']=['different']
    if bad=='config': r['input']['model']='wrong'
    if bad=='status': r['status']='error'
    if bad=='vector': r['query_vector']=[0.0]*DIMENSION
    if bad=='hits': r['hits'][0]['text']='tampered'
    write_json(path,record)
    if bad=='missing': path.unlink()
    with pytest.raises((ValueError,KeyError,TypeError)):
        core.replay(folder,index)


@pytest.mark.parametrize('score,decision',[(.499999,'fail'),(.5,'pass'),(.8,'pass')])
def test_gate_boundary(score,decision):
    assert core.gate([{'score':score},{'score':.1}])['decision']==decision
    assert core.gate([])['reason']=='no_hits'
    with pytest.raises(ValueError): core.gate([{'score':float('nan')}])


@pytest.mark.parametrize('change,code',[
    ('empty_answer','empty_answer'),('empty_sources','empty_sources'),
    ('empty_citations','empty_citations'),('source','source_mismatch'),
    ('section','section_mismatch'),('unsent','unknown_chunk_id'),
    ('sets','chunk_sets_mismatch'),('space','quote_not_found'),
    ('case','quote_not_found'),('unicode','quote_not_found'),
    ('empty_quote','empty_quote'),('long','quote_too_long'),
    ('duplicate_source','duplicate_source'),('duplicate_quote','duplicate_citation'),
])
def test_validation_failures_preserve_candidate(context,change,code):
    obj=answer(context)
    if change=='empty_answer': obj['answer']=' \n'
    if change=='empty_sources': obj['sources']=[]
    if change=='empty_citations': obj['citations']=[]
    if change in ('source','section'): obj['sources'][0][change]='wrong'
    if change=='unsent':
        obj['sources'][0]['chunk_id']=obj['citations'][0]['chunk_id']='indexed-but-unsent'
    if change=='sets': obj['citations'][0]['chunk_id']=context[1]['chunk_id']
    if change=='space': obj['citations'][0]['quote']='Exact spacing'
    if change=='case': obj['citations'][0]['quote']='fact 0.'
    if change=='unicode': obj['citations'][0]['quote']='e\u0301'
    if change=='empty_quote': obj['citations'][0]['quote']=' '
    if change=='long': obj['citations'][0]['quote']='x'*401
    if change=='duplicate_source': obj['sources']*=2
    if change=='duplicate_quote': obj['citations']*=2
    raw=json.dumps(obj)
    validation,result=core.validate(raw,context)
    assert result is None and validation['status']=='validation_failed'
    assert code in [e['code'] for e in validation['errors']]
    assert json.dumps(obj)==raw


def test_literal_quotes_and_abstention(context):
    obj=answer(context)
    obj['citations'][0]['quote']='Fact 0.\nExact  spacing é.'
    assert core.validate(json.dumps(obj),context)[1]==obj
    assert core.validate(json.dumps(core.abstention()),context)[1]==core.abstention()
    for change in ('answer','sources','citations'):
        invalid=core.abstention()
        invalid[change]=answer(context)[change]
        assert core.validate(json.dumps(invalid),context)[1] is None
    assert core.validate('{"status":"answered","status":"answered"}',context)[1] is None
    obj['extra']='forbidden'
    assert core.validate(json.dumps(obj),context)[1] is None


class Client:
    def __init__(self, mode='answer'):
        self.mode=mode
        self.calls=[]
        self.observed_output=None

    async def complete(self, messages, config):
        self.calls.append((messages,config))
        context=json.loads(messages[0].content)['context']
        if self.mode=='crash': raise RuntimeError('unexpected interruption')
        obj=answer(context)
        if self.mode=='abstain': obj=core.abstention()
        if self.mode=='invalid': obj['sources'][0]['source']='fabricated.md'
        if self.mode=='unsupported': obj['answer']='Android automatically repeats Send.'
        raw=json.dumps(obj,ensure_ascii=False)
        self.observed_output={'response_id':'fixture-response','status':'completed',
            'output':[{'type':'message','content':[{'type':'output_text','text':raw}]}]}
        if self.mode in {'incomplete','refused','error','timeout'}:
            return LlmResult('error' if self.mode=='timeout' else self.mode,
                             error_code='llm_timeout' if self.mode=='timeout' else 'fixture_error')
        return LlmResult('completed',reply=raw)


def saved(tmp_path,baseline,mode='answer'):
    b,rs=core.replay(*baseline)
    client=Client(mode)
    folder=asyncio.run(experiment.run_eval(b,rs,output_root=tmp_path/'results',
                                         client=client,progress=lambda _:None))
    return folder,client


def test_full_eval_evidence_and_abstention(tmp_path,baseline):
    folder,client=saved(tmp_path,baseline)
    run,review,rs=report.load_saved(folder)
    assert len(client.calls)==9 and run['status']=='finished'
    assert all(len(json.loads(m[0].content)['context'])==5 for m,_ in client.calls)
    assert all(r['retrieval']['embedding_attempted'] is False for r in rs.values())
    assert rs['Q01']['normalized_result']['status']=='answered'
    assert rs['Q01']['validation']['status']=='passed'
    assert review['questions']['Q01']['answer_supported_by_citations']=='pending'
    q=rs['Q10']
    assert q['normalized_result']==core.abstention() and q['abstention_origin']=='runtime_gate'
    assert q['generation']['attempted'] is False and q['generation']['request'] is None
    assert q['generation']['observed_output'] is None and q['actual_model_context']==[]
    assert len(q['retrieval']['hits'])==5
    assert review['questions']['Q10']['citations_exact']=='N/A'


@pytest.mark.parametrize('mode',['abstain','invalid','incomplete','refused','error','timeout'])
def test_failures_and_model_abstention_without_retry(tmp_path,baseline,mode):
    folder,client=saved(tmp_path,baseline,mode)
    _,review,rs=report.load_saved(folder)
    r=rs['Q01']
    assert len(client.calls)==9 and r['generation']['attempted'] is True
    assert r['generation']['observed_output']['response_id']=='fixture-response'
    if mode=='abstain':
        assert r['normalized_result']==core.abstention()
        assert r['abstention_origin']=='model_semantic'
        assert review['questions']['Q01']['citations_exact']=='N/A'
        assert 'GENERATION CALL: YES' in report.render(folder,question_id='Q01',video=True)
    else:
        assert r['normalized_result'] is None and r['abstention_origin'] is None
        assert r['processing_status']=={'invalid':'validation_failed','timeout':'unknown'}.get(mode,mode)
        if mode=='invalid':
            assert 'fabricated.md' in r['generation']['outcome']['reply']
            assert review['questions']['Q01']['citations_exact']=='yes'
            assert 'NO VALIDATED ANSWER' in report.render(folder,question_id='Q01',video=True)
            review['reviewer']='fixture reviewer'
            review['questions']['Q01'].update(status='reviewed',answer_supported_by_citations='yes')
            write_json(folder/'review.json',review)
            assert 'yes (raw only)' in report.render(folder,video=True)
            assert 'RAW CANDIDATE ONLY' in report.render(folder,question_id='Q01',video=True)


@pytest.mark.parametrize('stage',['initial','dispatch','raw','review'])
def test_storage_failure_stops_calls(tmp_path,baseline,monkeypatch,stage):
    b,rs=core.replay(*baseline)
    client=Client()
    original=experiment.write_json
    def fail(path,value):
        if ((stage=='initial' and path.name=='run.json')
                or (path.name=='Q01.json' and stage=='dispatch' and value['generation']['attempted'])
                or (path.name=='Q01.json' and stage=='raw' and 'outcome' in value['generation'])
                or (path.name=='review.json' and stage=='review' and len(client.calls)==1)):
            raise OSError('storage failure')
        original(path,value)
    monkeypatch.setattr(experiment,'write_json',fail)
    with pytest.raises(OSError):
        asyncio.run(experiment.run_eval(b,rs,output_root=tmp_path/'results',client=client,progress=lambda _:None))
    assert len(client.calls)==(1 if stage in {'raw','review'} else 0)
    if stage=='raw':
        record=read_json(next((tmp_path/'results').glob('*/Q01.json')))
        assert record['generation']['status']=='unknown' and 'outcome' not in record['generation']


def test_interruption_retains_unknown(tmp_path,baseline):
    b,rs=core.replay(*baseline)
    client=Client('crash')
    with pytest.raises(RuntimeError):
        asyncio.run(experiment.run_eval(b,rs,output_root=tmp_path/'results',client=client,progress=lambda _:None))
    folder=next((tmp_path/'results').iterdir())
    run,_,records=report.load_saved(folder)
    assert run['status']=='partial' and records['Q01']['processing_status']=='unknown'
    assert records['Q02']['generation']['attempted'] is False and len(client.calls)==1


def test_raw_saved_before_validation(tmp_path,baseline,monkeypatch):
    def validate_failure(*args): raise RuntimeError('validation interrupted')
    monkeypatch.setattr(experiment,'validate',validate_failure)
    with pytest.raises(RuntimeError): saved(tmp_path,baseline)
    r=read_json(next((tmp_path/'results').glob('*/Q01.json')))
    assert r['generation']['status']=='completed'
    assert r['generation']['observed_output']['output']
    assert r['processing_status']=='unknown' and r['normalized_result'] is None


def test_exact_but_unsupported_manual_review(tmp_path,baseline):
    folder,_=saved(tmp_path,baseline,'unsupported')
    run,review,records=report.load_saved(folder)
    item=review['questions']['Q01']
    assert records['Q01']['validation']['status']=='passed'
    assert item['citations_exact']=='yes' and item['answer_supported_by_citations']=='pending'
    review['reviewer']='fixture manual reviewer'
    item.update(status='reviewed',answer_supported_by_citations='no',
        unsupported_claims=[dict(claim='Android automatically repeats Send.',notes='Quote only says Fact 0.')])
    write_json(folder/'review.json',review)
    text=report.render(folder,question_id='Q01',video=True)
    assert 'citation exactness=yes' in text and 'no | review=reviewed' in text
    assert 'UNSUPPORTED:' in text
    item['sources_present']='no'
    write_json(folder/'review.json',review)
    with pytest.raises(ValueError,match='mechanical'): report.load_saved(folder)
    item['sources_present']='yes'
    item['answer_supported_by_citations']='yes'
    write_json(folder/'review.json',review)
    with pytest.raises(ValueError,match='contradicts'): report.load_saved(folder)
    review['eval_id']='other'
    write_json(folder/'review.json',review)
    with pytest.raises(ValueError,match='another run'): report.load_saved(folder)


def test_cli_report_is_keyless_and_self_contained(tmp_path,baseline,monkeypatch,capsys):
    folder,_=saved(tmp_path,baseline)
    before={p.name:p.read_bytes() for p in folder.iterdir()}
    monkeypatch.delenv('OPENAI_API_KEY',raising=False)
    cli=runpy.run_path(str(ROOT/'backend/scripts/day24_rag.py'),run_name='day24_test')
    def forbidden(*args,**kwargs): raise AssertionError('Report accessed provider/index/baseline')
    cli['execute'].__globals__['read_index']=forbidden
    cli['execute'].__globals__['replay']=forbidden
    from app.first_rag.client import ObservedClient
    monkeypatch.setattr(ObservedClient,'__init__',forbidden)
    for qid in ('Q01','Q10'):
        args=cli['parser']().parse_args(['report',str(folder),'--question',qid,'--video'])
        asyncio.run(cli['execute'](args))
        text=capsys.readouterr().out
        if qid=='Q01':
            for section in ('QUESTION','GATE PASS','ANSWER','SOURCES','CITATIONS','VALIDATION','SEMANTIC SUPPORT'):
                assert section in text
        else:
            assert 'GATE FAIL' in text and 'GENERATION CALL: NO' in text and core.ABSTENTION in text
    assert 'FORENSIC RECORD' in report.render(folder,question_id='Q01',full=True)
    assert 'pending' in report.render(folder,video=True)
    assert before=={p.name:p.read_bytes() for p in folder.iterdir()}
    with pytest.raises(SystemExit): cli['parser']().parse_args(['report',str(folder),'--video','--full'])
