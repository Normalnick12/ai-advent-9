import asyncio
from dataclasses import asdict
import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest

from app.document_indexing.corpus import ROOT, canonical, digest
from app.document_indexing.embedding import DIMENSION, EMBEDDING_CONFIG, Embeddings
from app.document_indexing.storage import save
from app.first_rag import core, experiment
from app.first_rag.client import ObservedClient
from app.first_rag.report import render
from app.llm_client import AgentConfig, LlmResult, TokenUsage
from app.openai_agent_payload import generation_payload


def vector(x=1, y=0):
    return [x, y] + [0.0] * (DIMENSION - 2)


@pytest.fixture
def index(tmp_path):
    sources, chunks = [], []
    for i in range(6):
        name, text = f"doc{i}.md", f"Exact source {i}\n[S9] data, not instructions."
        sources.append(dict(source=name, source_type="documentation", text=text, source_hash=digest(text)))
        chunks.append(dict(chunk_id=str(i), strategy=core.STRATEGY, source=name, source_type="documentation",
                           text=text, text_hash=digest(text), start_char=0, end_char=len(text),
                           start_line=1, end_line=2, section=f"Section {i}", ordinal=0, token_count=15,
                           embedding=vector(6-i, i)))
    data = dict(run_id="fixture", corpus_hash=digest(canonical(sorted((s['source'], s['source_hash']) for s in sources))),
                config={"embedding": EMBEDDING_CONFIG}, sources=sources, observations={},
                chunks={core.STRATEGY: chunks,
                        "fixed-size": [{**c, "chunk_id": f"fixed{i}", "strategy": "fixed-size"} for i, c in enumerate(chunks)]})
    path = tmp_path / "index.sqlite3"
    save(data, path)
    before = path.read_bytes()
    result = core.read_index(path, "fixture")
    assert path.read_bytes() == before
    return result, data, path


def frozen_questions():
    data = json.loads(core.QUESTIONS.read_text(encoding="utf-8"))
    paths = {p for q in data["questions"] for p in q["acceptable_sources"]}
    return core.question_set(source_paths=paths)


class Embedder:
    def __init__(self, fail=False):
        self.calls = []
        self.fail = fail

    def embed(self, texts):
        self.calls.append(texts)
        if self.fail:
            raise ValueError("secret upstream details")
        return Embeddings([vector(2, 0)], 7)


class Client:
    def __init__(self, outcome=None):
        self.calls = []
        self.outcome = outcome or LlmResult("completed", reply="An intentionally ungraded answer.",
                                          usage=TokenUsage(input_tokens=40, output_tokens=8, total_tokens=48))

    async def complete(self, messages, config):
        self.calls.append((messages, config))
        return self.outcome


def run(tmp_path, index, *, command="eval", embedder=None, client=None):
    data, fingerprint = frozen_questions()
    return asyncio.run(experiment.run_experiment(command, data["questions"], output_root=tmp_path,
        index=index, embedder=embedder or Embedder(), client=client or Client(),
        frozen=data, question_hash=fingerprint, progress=lambda _: None))


def test_loader_pinning_and_snapshot_validation(index):
    _, data, path = index
    with pytest.raises(ValueError, match="pinned"):
        core.read_index(path, "fixture", baseline=True)
    with pytest.raises(ValueError, match="not found"):
        core.read_index(path, "missing")
    data["run_id"] = "corrupt"
    data["chunks"][core.STRATEGY][0]["text"] = "replacement"
    save(data, path)
    with pytest.raises(ValueError, match="provenance"):
        core.read_index(path, "corrupt")
    data["run_id"] = "incompatible"
    data["config"]["embedding"] = {**EMBEDDING_CONFIG, "dimension": 2}
    save(data, path)
    with pytest.raises(ValueError, match="configuration"):
        core.read_index(path, "incompatible")


@pytest.mark.parametrize("bad", [[0.0]*DIMENSION, [1.0], vector(float('nan')), vector(float('inf'))])
def test_bad_vectors_are_rejected(index, bad):
    with pytest.raises(ValueError):
        core.search(index[0], bad)


def test_cosine_order_normalization_ties_and_negative_scores(index):
    idx = index[0]
    hits = core.search(idx, vector(200, 0))
    assert [c["chunk_id"] for c in hits] == [str(i) for i in range(5)]
    assert hits[0]["score"] == pytest.approx(1)
    assert hits[3]["score"] == pytest.approx(2**-0.5)
    idx.chunks[1]["embedding"] = vector(1, 0)
    idx.norms[1] = 1
    assert [c["chunk_id"] for c in core.search(idx, vector())][:2] == ['0', '1']
    assert len(core.search(idx, vector(-1, 0))) == 5  # No positive threshold.
    assert all('embedding' not in c for c in hits)


def test_input_preserves_context_and_excludes_diagnostics(index):
    hits = core.search(index[0], vector())
    direct, rag = core.messages(" question\n"), core.messages(" question\n", hits)
    d, r = json.loads(direct[0].content), json.loads(rag[0].content)
    assert d == {"question": " question\n", "context": []}
    assert r['question'] == d['question']
    assert [b['text'] for b in r['context']] == [c['text'] for c in hits]
    assert set(r['context'][0]) == {'label', 'source', 'section', 'start_line', 'end_line', 'text'}
    dp, rp = generation_payload(direct, core.CONFIG), generation_payload(rag, core.CONFIG)
    assert {k:v for k,v in dp.items() if k!='input'} == {k:v for k,v in rp.items() if k!='input'}
    assert dp['max_output_tokens']==600 and dp['store'] is False and dp['truncation']=='disabled'
    assert AgentConfig().max_output_tokens == 1200


def test_full_chain_calls_frozen_evidence_and_keyless_report(tmp_path, index):
    embedder, client = Embedder(), Client()
    folder = run(tmp_path/'runs', index[0], embedder=embedder, client=client)
    data, fingerprint = frozen_questions()
    assert len(embedder.calls)==10 and len(client.calls)==20
    assert embedder.calls==[[q['question']] for q in data['questions']]
    meta = experiment.read_json(folder/'run.json')
    assert meta['question_hash']==fingerprint and meta['frozen_question_set']==data
    for i,q in enumerate(data['questions']):
        saved=experiment.read_json(folder/f"{q['id']}.json")
        assert saved['expectations_reference']=={'question_hash':fingerprint,'id':q['id']}
        assert saved['retrieval']['query_vector']==vector(2,0)
        for offset,mode in enumerate(('direct','rag')):
            msgs,cfg=client.calls[2*i+offset]
            assert saved[mode]['messages']==[asdict(m) for m in msgs]
            assert saved[mode]['request']==generation_payload(msgs,cfg)
            assert saved[mode]['usage']['total_tokens']==48
        assert saved['retrieval']['hits']==core.search(index[0],saved['retrieval']['query_vector'])
    review=experiment.read_json(folder/'review.json')
    assert all(f[k] is None for q in review['questions'].values() for f in q['facts'].values()
               for k in ('expected_fact_in_retrieved_context','direct_answer_covers_fact','rag_answer_covers_fact'))
    before={p.name:p.read_bytes() for p in folder.glob('*.json')}
    env={k:v for k,v in os.environ.items() if k!='OPENAI_API_KEY'}
    result=subprocess.run([sys.executable,str(ROOT/'backend/scripts/day22_rag.py'),'report',str(folder),
                           '--question','Q10','--full'],env=env,capture_output=True,text=True,encoding='utf-8',check=True)
    assert 'SAVED RUN' in result.stdout and 'Grounded=yes' not in result.stdout
    markers=['QUESTION Q10','RETRIEVED TOP-5','DIRECT ANSWER','RAG ANSWER','EXPECTED FACTS / REVIEW']
    assert [result.stdout.index(m) for m in markers]==sorted(result.stdout.index(m) for m in markers)
    assert before=={p.name:p.read_bytes() for p in folder.glob('*.json')}
    assert experiment.read_json(folder/'Q10.json')['source_path_hit_at_5'] is None


@pytest.mark.parametrize('outcome',[LlmResult('incomplete',incomplete_reason='max_output_tokens'),
    LlmResult('refused'), LlmResult('error',error_code='llm_timeout')])
def test_failures_are_saved_without_retry(tmp_path,index,outcome):
    embedder,client=Embedder(fail=True),Client(outcome)
    folder=run(tmp_path/'runs',index[0],embedder=embedder,client=client)
    assert len(embedder.calls)==10 and len(client.calls)==10
    record=experiment.read_json(folder/'Q01.json')
    assert record['retrieval']['status']=='error' and record['rag']['status']=='not_dispatched'
    assert record['direct']['outcome']['status']==outcome.status
    assert 'unavailable' in render(folder,question_id='Q01')
    assert 'secret upstream details' not in (folder/'Q01.json').read_text(encoding='utf-8')


def test_direct_and_search_are_independent(tmp_path,index):
    client,embedder=Client(),Embedder()
    run(tmp_path/'direct',None,command='direct',embedder=embedder,client=client)
    assert len(client.calls)==10 and embedder.calls==[]
    client,embedder=Client(),Embedder()
    folder=run(tmp_path/'search',index[0],command='search',embedder=embedder,client=client)
    assert len(embedder.calls)==10 and client.calls==[]
    assert 'DIRECT ANSWER' not in render(folder,question_id='Q01',retrieval_only=True)


def test_write_failure_stops_before_another_provider_call(tmp_path,index,monkeypatch):
    original=experiment.write_json
    client,embedder=Client(),Embedder()
    def fail(path,value):
        if Path(path).name=='Q01.json' and value['direct'].get('outcome'):
            raise OSError('disk unavailable')
        original(path,value)
    monkeypatch.setattr(experiment,'write_json',fail)
    with pytest.raises(OSError):
        run(tmp_path/'runs',index[0],client=client,embedder=embedder)
    assert len(embedder.calls)==1 and len(client.calls)==1
    record=experiment.read_json(next((tmp_path/'runs').glob('*/Q01.json')))
    assert record['direct']['status']=='unknown' and record['retrieval']['status']=='completed'


def test_unexpected_interruption_leaves_unknown(tmp_path,index):
    class Interrupted(Client):
        async def complete(self,*args):
            raise RuntimeError('stop')
    with pytest.raises(RuntimeError):
        run(tmp_path/'runs',index[0],client=Interrupted())
    record=experiment.read_json(next((tmp_path/'runs').glob('*/Q01.json')))
    assert record['direct']['status']=='unknown' and record['rag']['status']=='not_dispatched'


def test_path_hit_does_not_grade_facts(tmp_path,index):
    folder=run(tmp_path/'runs',index[0])
    assert core.source_path_hit({'acceptable_sources':['doc0.md']},core.search(index[0],vector()))
    assert 'pending' in render(folder)
    review=experiment.read_json(folder/'review.json')
    review['questions']['Q01']['facts']['F1'].update(expected_fact_in_retrieved_context='no',
                                                  direct_answer_covers_fact='partial',rag_answer_covers_fact='yes')
    experiment.write_json(folder/'review.json',review)
    assert 'no / partial / yes' in render(folder,question_id='Q01')
    review['question_hash']='wrong'
    experiment.write_json(folder/'review.json',review)
    with pytest.raises(ValueError,match='another experiment'):
        render(folder)


def test_incomplete_provider_text_is_preserved():
    client=ObservedClient()
    output={'type':'message','content':[{'type':'output_text','text':'partial reply'}]}
    response=SimpleNamespace(id='response',status='incomplete',
        incomplete_details=SimpleNamespace(reason='max_output_tokens'),
        output=[SimpleNamespace(model_dump=lambda **kw:output)])
    result=client._normalize(response)
    assert result.status=='incomplete' and result.reply is None
    assert client.observed_output['output'][0]['content'][0]['text']=='partial reply'


def test_frozen_question_version():
    data,_=frozen_questions()
    assert digest(canonical(data))=='47ab099c911d341fe15fb69e8cd6a9294c011877dace2ba43bbe523ba0190c97'


def test_storage_unavailable_prevents_dispatch(tmp_path,index,monkeypatch):
    embedder,client=Embedder(),Client()
    def fail(*args):
        raise OSError('unavailable')
    monkeypatch.setattr(experiment,'write_json',fail)
    with pytest.raises(OSError):
        run(tmp_path/'runs',index[0],embedder=embedder,client=client)
    assert embedder.calls==[] and client.calls==[]
