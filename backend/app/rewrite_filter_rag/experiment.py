"""Two sequential stages; saved retrieval is never dispatched again by compare."""
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from uuid import uuid4

from app.agent import SimpleAgent
from app.document_indexing.corpus import canonical, digest
from app.document_indexing.embedding import EMBEDDING_CONFIG
from app.first_rag.core import CONFIG, check_question, messages, search, vector_norm
from app.first_rag.experiment import phase, read_json, write_json
from app.llm_client import ConversationMessage
from app.openai_agent_payload import generation_payload
from .core import REWRITE_CONFIG, TOP_N, experiment_config, retrieval_hash, select


def review_template(run):
    return dict(schema_version=1, eval_id=run['eval_id'], question_hash=run['question_hash'],
                reviewer=None, questions={q['id']: dict(
                    status='pending', rewrite_preserves_intent=None,
                    rewrite_added_project_assumption=None, rewrite_note='',
                    facts={f['id']: dict(expected_fact_in_retrieved_context=None,
                                         enhanced_answer_covers_fact=None, notes='')
                           for f in q['expected_facts']}, claims=[], diagnosis=[], notes='')
                    for q in run['questions']})


async def generation(branch, inputs, config, client, save):
    branch.update(status='unknown', attempted=True, messages=[asdict(m) for m in inputs],
                  config=asdict(config), request=generation_payload(inputs, config))
    save()
    started = perf_counter()
    outcome = await SimpleAgent(client, config).generate(inputs)
    branch.update(status='unknown' if outcome.error_code == 'llm_timeout' else outcome.status,
                  outcome=asdict(outcome), usage=asdict(outcome.usage) if outcome.usage else None,
                  observed_output=getattr(client, 'observed_output', None),
                  elapsed_seconds=perf_counter()-started)
    save()
    return outcome


async def retrieve(baseline, index, *, output_root, client, embedder, progress=print):
    folder = Path(output_root) / str(uuid4())
    folder.mkdir(parents=True, exist_ok=False)
    run = dict(schema_version=1, eval_id=folder.name, created_at=datetime.now(timezone.utc).isoformat(),
               index=index.provenance, config=experiment_config(),
               question_hash=baseline['run']['question_hash'], questions=baseline['run']['questions'],
               retrieve_status='partial', compare_status='not_dispatched',
               baseline_hash=digest(canonical(baseline)))
    write_json(folder/'baseline.json', baseline)
    write_json(folder/'run.json', run)
    write_json(folder/'review.json', review_template(run))
    records = {}
    for q in run['questions']:
        records[q['id']] = dict(id=q['id'], original_question=q['question'], retrieval_query=None,
                               rewrite=phase(), embedding=phase(), enhanced=phase(),
                               retrieval=dict(status='not_computed', candidates=[], final_context=[]))
        write_json(folder/f"{q['id']}.json", records[q['id']])
    progress(f'Evidence: {folder}')
    for q in run['questions']:
        record = records[q['id']]
        path = folder/f"{q['id']}.json"

        def save():
            write_json(path, record)

        progress(f"{q['id']} ORIGINAL QUESTION: {q['question']}")
        outcome = await generation(record['rewrite'], (ConversationMessage('user', q['question']),),
                                   REWRITE_CONFIG, client, save)
        progress(f"{q['id']} rewrite: {record['rewrite']['status']}")
        if outcome.status != 'completed':
            record['retrieval']['reason'] = 'rewrite_unavailable'
            save()
            continue
        check_question(outcome.reply)
        record['retrieval_query'] = outcome.reply  # Exact text, including whitespace.
        progress(f"{q['id']} RETRIEVAL QUERY: {outcome.reply}")
        embedding = record['embedding']
        embedding.update(status='unknown', attempted=True,
                         input=dict(texts=[outcome.reply], **EMBEDDING_CONFIG))
        save()
        started = perf_counter()
        try:
            result = embedder.embed([outcome.reply])
        except ValueError:
            embedding.update(status='error', error_code='query_embedding_failed', provider_outcome='unknown')
        else:
            embedding['usage'] = result.usage
            try:
                if len(result.vectors) != 1:
                    raise ValueError('Expected one query vector')
                vector_norm(result.vectors[0])
                embedding.update(query_vector=result.vectors[0], status='completed')
                save()
                decisions, kept = select(search(index, result.vectors[0], top_k=TOP_N))
                record['retrieval'].update(status='completed', candidates=decisions, final_context=kept)
            except ValueError:
                record['retrieval'].update(status='error', error_code='invalid_query_vector_or_search')
        embedding['elapsed_seconds'] = perf_counter()-started
        save()
        progress(f"{q['id']} embedding: {embedding['status']}; retrieval: "
                 f"{record['retrieval']['status']}; kept={len(record['retrieval']['final_context'])}")
    run.update(retrieve_status='finished', retrieval_hash=retrieval_hash(records))
    write_json(folder/'run.json', run)
    return folder


def load_saved(folder):
    folder = Path(folder)
    run, baseline, review = [read_json(folder/f'{name}.json') for name in ('run', 'baseline', 'review')]
    if (run['schema_version'] != 1 or digest(canonical(baseline)) != run['baseline_hash']
            or baseline['run']['question_hash'] != run['question_hash']
            or baseline['run']['questions'] != run['questions']
            or (review['eval_id'], review['question_hash']) != (run['eval_id'], run['question_hash'])):
        raise ValueError('Saved experiment identity mismatch')
    records = {q['id']: read_json(folder/f"{q['id']}.json") for q in run['questions']}
    for q in run['questions']:
        r, item = records[q['id']], review['questions'][q['id']]
        if r['id'] != q['id'] or r['original_question'] != q['question']:
            raise ValueError('Original question mismatch')
        if item['status'] not in {'pending', 'reviewed'}:
            raise ValueError('Invalid review status')
        if (item['rewrite_preserves_intent'] not in {None, 'yes', 'partial', 'no'}
                or item['rewrite_added_project_assumption'] not in {None, 'yes', 'no'}):
            raise ValueError('Invalid rewrite review label')
        if set(item['facts']) != {f['id'] for f in q['expected_facts']}:
            raise ValueError('Invalid review fact IDs')
        for f in item['facts'].values():
            if any(f[k] not in {None, 'yes', 'partial', 'no'} for k in
                   ('expected_fact_in_retrieved_context', 'enhanced_answer_covers_fact')):
                raise ValueError('Invalid fact review label')
        if any(c['grounded_in_retrieved_context'] not in {'yes', 'no'} for c in item['claims']):
            raise ValueError('Invalid claim review label')
    if run['retrieve_status'] == 'finished' and retrieval_hash(records) != run['retrieval_hash']:
        raise ValueError('Saved retrieval changed')
    return run, baseline, review, records


async def compare(folder, *, client, progress=print):
    folder = Path(folder)
    run, baseline, review, records = load_saved(folder)
    if run['retrieve_status'] != 'finished' or run['config'] != experiment_config():
        raise ValueError('Retrieval/config is not ready')
    if run['compare_status'] != 'not_dispatched' or any(r['enhanced']['attempted'] for r in records.values()):
        raise ValueError('Compare already attempted; no replay')
    run['compare_status'] = 'partial'
    write_json(folder/'run.json', run)
    for q in run['questions']:
        record = records[q['id']]
        path = folder/f"{q['id']}.json"

        def save():
            write_json(path, record)

        if record['retrieval']['status'] != 'completed':
            record['enhanced']['reason'] = 'retrieval_unavailable'
            save()
            continue
        await generation(record['enhanced'], messages(record['original_question'],
                         record['retrieval']['final_context']), CONFIG, client, save)
        progress(f"{q['id']} enhanced: {record['enhanced']['status']}")
    run['compare_status'] = 'finished'
    write_json(folder/'run.json', run)
    return folder
