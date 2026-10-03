"""Read-only presentation; mechanical validity and semantic support stay separate."""
from collections import Counter
from copy import deepcopy
import json
from pathlib import Path
from textwrap import fill

from app.document_indexing.corpus import canonical, digest
from app.first_rag.experiment import read_json
from app.grounded_rag.core import abstention, context_from_request, gate, validate
from app.grounded_rag.experiment import mechanical, support_default


def load_saved(folder):
    folder=Path(folder)
    run,review=read_json(folder/'run.json'),read_json(folder/'review.json')
    if (review['eval_id'],review['question_hash']) != (run['eval_id'],run['question_hash']):
        raise ValueError('Review belongs to another run/question set')
    if (digest(canonical(run['frozen_question_set'])) != run['question_hash']
            or run['questions'] != run['frozen_question_set']['questions']):
        raise ValueError('Frozen questions changed')
    if set(review['questions']) != {q['id'] for q in run['questions']}:
        raise ValueError('Review question IDs differ')
    records={}
    for q in run['questions']:
        r=read_json(folder/f"{q['id']}.json")
        if (r['id'],r['question']) != (q['id'],q['question']):
            raise ValueError('Question checkpoint mismatch')
        if r['gate'] != gate(r['retrieval']['hits']):
            raise ValueError('Gate evidence mismatch')
        g=r['generation']
        if r['gate']['decision']=='fail':
            if (g['attempted'] or g['request'] is not None or g['observed_output'] is not None
                    or g['status']!='not_dispatched' or r['actual_model_context']
                    or r['normalized_result']!=abstention() or r['abstention_origin']!='runtime_gate'):
                raise ValueError('Invalid gate abstention evidence')
        elif g['attempted']:
            context=context_from_request(g['request'],q['question'],r['retrieval']['hits'])
            if context!=r['actual_model_context']:
                raise ValueError('Actual context mismatch')
            if r['processing_status'] in {'accepted','validation_failed'}:
                validation,result=validate(g['outcome']['reply'],context)
                origin='model_semantic' if result and result['status']=='insufficient_context' else None
                if (validation!=r['validation'] or result!=r['normalized_result']
                        or origin!=r['abstention_origin']):
                    raise ValueError('Validation evidence mismatch')
        elif r['normalized_result'] is not None:
            raise ValueError('Result without dispatch')
        item=review['questions'][q['id']]
        if item['status'] not in {'pending','reviewed'}:
            raise ValueError('Invalid manual review status')
        derived=mechanical(r)
        if item['status']=='reviewed':
            if not isinstance(review['reviewer'],str) or not review['reviewer'].strip():
                raise ValueError('Reviewed labels require reviewer identity')
            if any(item[k]!=v for k,v in derived.items()):
                raise ValueError('Manual mechanical labels differ from evidence')
        else:
            # An interruption can leave review one checkpoint behind the raw result.
            item.update(derived)
        support=item['answer_supported_by_citations']
        default=support_default(r)
        if default=='N/A':
            if support!='N/A': raise ValueError('Abstention support must be N/A')
        elif support not in {'yes','partial','no','pending','unavailable'}:
            raise ValueError('Invalid semantic support label')
        if item['status']=='reviewed' and r['normalized_result'] and default=='pending' and support not in {'yes','partial','no'}:
            raise ValueError('Reviewed answer requires semantic support label')
        for claim in item['unsupported_claims']:
            if not all(isinstance(claim[k],str) and claim[k].strip() for k in ('claim','notes')):
                raise ValueError('Unsupported claim requires text and notes')
        if support=='yes' and item['unsupported_claims']:
            raise ValueError('Support yes contradicts unsupported claims')
        if support in {'partial','no'} and not item['unsupported_claims']:
            raise ValueError('Support partial/no requires unsupported claims')
        if not set(item['facts']) <= {f['id'] for f in q['expected_facts']}:
            raise ValueError('Unknown expected fact ID')
        for fact in item['facts'].values():
            if (fact['correctness'] not in {'yes','partial','no','N/A','unavailable'}
                    or fact['coverage'] not in {'yes','partial','no','N/A','unavailable'}
                    or not isinstance(fact['notes'],str)):
                raise ValueError('Invalid expected-fact review')
        records[q['id']]=r
    return run,review,records


def semantic_label(item):
    return item['answer_supported_by_citations'] if item['status']=='reviewed' else 'pending'


def render(folder, *, question_id=None, full=False, video=False):
    run,review,records=load_saved(folder)
    lines=[f"SAVED RUN: {run['eval_id']} | traversal={run['status']}",
           'PIPELINE: frozen original Top-5 -> best-score gate 0.50 -> structured answer -> validation']
    if question_id is None:
        lines += [f"GENERATION CALLS: {sum(r['generation']['attempted'] for r in records.values())} | "
                  'NEW QUERY EMBEDDINGS: 0 (cached vectors)',
                  'TECHNICAL: '+str(dict(Counter(r['generation']['status'] for r in records.values()))),
                  'PROCESSING: '+str(dict(Counter(r['processing_status'] for r in records.values()))),
                  'VALIDATED RESPONSES: '+str(dict(Counter(r['normalized_result']['status']
                      for r in records.values() if r['normalized_result']))),
                  'ABSTENTION ORIGIN: '+str(dict(Counter(r['abstention_origin'] for r in records.values() if r['abstention_origin']))),
                  '', 'ID  | BEST     | GATE | RESULT               | PROVENANCE | EXACT | SUPPORT / REVIEW']
        for qid,r in records.items():
            result=(r['normalized_result'] or {}).get('status',r['processing_status'])
            best=r['gate']['best_score']
            score=f'{best:.6f}' if best is not None else 'N/A'
            item=review['questions'][qid]
            support=semantic_label(item)
            if r['processing_status']=='validation_failed' and item['status']=='reviewed':
                support+=' (raw only)'
            lines.append(f"{qid} | {score:8} | {r['gate']['decision'].upper():4} | {result:20} | "
                f"{r['validation']['provenance']:10} | {item['citations_exact']:5} | "
                f"{support} / {item['status']}")
        lines += ['',fill(run['limitation'],100),'Details: report RESULT --question Qxx --video; forensic: --full']
        if not full:
            return '\n'.join(lines)
    selected=run['questions'] if question_id is None else [q for q in run['questions'] if q['id']==question_id]
    if not selected: raise ValueError('Unknown question ID')
    for q in selected:
        r,item=records[q['id']],review['questions'][q['id']]
        best=r['gate']['best_score']
        lines += ['',f"QUESTION {q['id']}",fill(q['question'],100),'',
                  f"GATE {r['gate']['decision'].upper()} | best={best:.6f} | threshold={r['gate']['threshold']:.2f}"
                  if best is not None else 'GATE FAIL | best=N/A | threshold=0.50',
                  'GENERATION CALL: '+('YES' if r['generation']['attempted'] else 'NO'),
                  f"ORIGIN: {r['abstention_origin'] or 'generation'} | processing={r['processing_status']}"]
        result=r['normalized_result']
        if result:
            lines += ['', 'ANSWER | '+result['status'],fill(result['answer'],100), '', 'SOURCES']
            ids={c['chunk_id']:c['label'] for c in r['actual_model_context']}
            for source in result['sources']:
                cid=source['chunk_id']
                lines += [f"{ids[cid]} {source['source']}",f"  section: {source['section']}",
                          f"  chunk_id{' prefix (display only)' if video else ''}: {cid[:12] if video else cid}"]
            if not result['sources']: lines.append('[] (correct for insufficient_context)')
            lines += ['', 'CITATIONS']
            for i,c in enumerate(result['citations'],1):
                # Preserve literal quote, including line breaks/spacing, even in video.
                lines += [f"C{i} -> {ids[c['chunk_id']]}",c['quote']]
            if not result['citations']: lines.append('[] (correct for insufficient_context)')
        else:
            lines += ['', 'NO VALIDATED ANSWER | '+r['processing_status']]
            if not video:
                lines += ['RAW CANDIDATE / UNVALIDATED:',
                          (r['generation'].get('outcome') or {}).get('reply') or '[No complete text]']
        lines += ['', 'VALIDATION',
                  f"contract={r['validation']['status']} | provenance={r['validation']['provenance']} | "
                  f"citation exactness={r['validation']['citation_exactness']}"]
        lines.extend(f"{e['field']}: {e['code']}" for e in r['validation']['errors'])
        lines += ['', 'SEMANTIC SUPPORT (manual' + ('; RAW CANDIDATE ONLY)' if r['processing_status']=='validation_failed' else ')'),
                  f"{semantic_label(item)} | review={item['status']} | reviewer={review['reviewer'] or 'pending'}",
                  f"sources present={item['sources_present']} | citations present={item['citations_present']}",
                  fill(item['notes'],100)]
        for claim in item['unsupported_claims']:
            lines += [fill('UNSUPPORTED: '+claim['claim'],100),fill(claim['notes'],100)]
        if not video:
            lines += ['', 'EXPECTED FACTS / CORRECTNESS / COVERAGE']
            for fact in q['expected_facts']:
                lines += [fact['id']+': '+fact['text'],str(item['facts'].get(fact['id'],'not reviewed'))]
            lines += ['', 'RETRIEVED TOP-5']
            for h in r['retrieval']['hits']:
                lines += [f"r{h['rank']} {h['score']:.9f} | {h['source']} | {h['chunk_id']}",h['section']]
                if full: lines.append(h['text'])
        if full:
            forensic=deepcopy(r)
            forensic['retrieval'].pop('query_vector',None)  # Vector remains in Qxx.json.
            lines += ['', 'FORENSIC RECORD (query vector in Qxx.json)',
                      json.dumps(forensic,ensure_ascii=False,indent=2)]
    return '\n'.join(lines)
