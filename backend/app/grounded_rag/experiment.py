"""One frozen run, with durable dispatch checkpoints and no repair or retry."""
from copy import deepcopy
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from uuid import uuid4

from app.first_rag.experiment import phase, write_json
from app.grounded_rag.core import (CONFIG, LIMITATION, THRESHOLD, abstention,
    context_from_request, gate, messages, parse, validate)
from app.openai_agent_payload import generation_payload


def mechanical(record):
    result = record['normalized_result']
    if result is None:
        reply = (record['generation'].get('outcome') or {}).get('reply')
        try:
            result = parse(reply)
        except (ValueError, TypeError):
            return dict(sources_present='unavailable', citations_present='unavailable',
                        citations_exact='unavailable')
    return dict(sources_present='yes' if result['sources'] else 'no',
                citations_present='yes' if result['citations'] else 'no',
                citations_exact=record['validation']['citation_exactness'])


def support_default(record):
    result = record['normalized_result']
    if result and result['status'] == 'insufficient_context':
        return 'N/A'
    return 'pending' if result else 'unavailable'


def review_template(run, records):
    return dict(schema_version=1, eval_id=run['eval_id'], question_hash=run['question_hash'],
        reviewer=None, questions={qid: dict(status='pending', **mechanical(r),
            answer_supported_by_citations=support_default(r), unsupported_claims=[], facts={}, notes='')
            for qid, r in records.items()})


async def run_eval(baseline, retrievals, *, output_root, client, progress=print):
    folder = Path(output_root)/str(uuid4())
    folder.mkdir(parents=True, exist_ok=False)
    old = baseline['run']
    run = dict(schema_version=1, eval_id=folder.name, created_at=datetime.now(timezone.utc).isoformat(),
        status='partial', index=deepcopy(old['index']), baseline=deepcopy(baseline['provenance']),
        questions=deepcopy(old['questions']), frozen_question_set=deepcopy(old['frozen_question_set']),
        question_hash=old['question_hash'], retrieval_mode='cached_original_query_vector',
        threshold=THRESHOLD, config=asdict(CONFIG), limitation=LIMITATION)
    write_json(folder/'run.json', run)
    records = {}
    for q in run['questions']:
        retrieval = deepcopy(retrievals[q['id']])
        if retrieval['status'] != 'completed':
            raise ValueError('Retrieval unavailable; not semantic abstention')
        r = dict(id=q['id'], question=q['question'], retrieval=retrieval, gate=gate(retrieval['hits']),
            actual_model_context=[], generation={**phase(), 'request':None, 'observed_output':None},
            processing_status='pending', abstention_origin=None, normalized_result=None,
            validation=dict(status='not_run',errors=[],provenance='unavailable',citation_exactness='unavailable'))
        if r['gate']['decision']=='fail':
            r.update(processing_status='accepted', abstention_origin='runtime_gate',
                     normalized_result=abstention())
            r['generation']['reason']=r['gate']['reason']
            r['validation']=dict(status='runtime_gate',errors=[],provenance='N/A',citation_exactness='N/A')
        records[q['id']]=r
        write_json(folder/f"{q['id']}.json",r)
    review=review_template(run,records)
    write_json(folder/'review.json',review)
    progress(f'Evidence: {folder}')
    for q in run['questions']:
        r=records[q['id']]
        if r['gate']['decision']=='fail':
            progress(f"{q['id']} gate FAIL | GENERATION CALL: NO")
            continue
        inputs=messages(q['question'],r['retrieval']['hits'])
        request=generation_payload(inputs,CONFIG)
        r['actual_model_context']=context_from_request(request,q['question'],r['retrieval']['hits'])
        r['generation'].update(status='unknown',attempted=True,request=request)
        r['processing_status']='unknown'
        write_json(folder/f"{q['id']}.json",r)
        progress(f"{q['id']} gate PASS | generation dispatch")
        started=perf_counter()
        # Unexpected exception stops traversal; the last durable checkpoint remains unknown.
        outcome=await client.complete(inputs,CONFIG)
        r['generation'].update(status='unknown' if outcome.error_code=='llm_timeout' else outcome.status,
            outcome=asdict(outcome), usage=asdict(outcome.usage) if outcome.usage else None,
            observed_output=deepcopy(getattr(client,'observed_output',None)),
            elapsed_seconds=perf_counter()-started)
        write_json(folder/f"{q['id']}.json",r)  # Raw evidence precedes parsing/validation.
        if outcome.status=='completed':
            r['validation'],r['normalized_result']=validate(outcome.reply,r['actual_model_context'])
            r['processing_status']='accepted' if r['normalized_result'] else 'validation_failed'
            if r['normalized_result'] and r['normalized_result']['status']=='insufficient_context':
                r['abstention_origin']='model_semantic'
        else:
            r['processing_status']=r['generation']['status']
        write_json(folder/f"{q['id']}.json",r)
        review['questions'][q['id']].update(**mechanical(r),
            answer_supported_by_citations=support_default(r))
        write_json(folder/'review.json',review)
        progress(f"{q['id']} {r['processing_status']} | "
                 f"{(r['normalized_result'] or {}).get('status',r['generation']['status'])}")
    run['status']='finished'
    write_json(folder/'run.json',run)
    return folder
