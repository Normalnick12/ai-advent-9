from collections import Counter

from app.first_rag.report import grounded
from .experiment import load_saved


def fact_cell(item, field, available=True):
    return ','.join(f"{fid}:{v[field] or 'pending'}" for fid, v in item['facts'].items()) if available else 'unavailable'


def label(value, available):
    return (value or 'pending') if available else 'unavailable'


def answer(lines, title, branch):
    lines.extend(['', f"{title} | {branch['status']}",
                  branch.get('outcome', {}).get('reply') or '[No completed answer]',
                  f"Usage: {branch['usage']}"])
    if branch['status'] != 'completed':
        lines.append(f"Technical details: {branch.get('outcome', branch.get('reason'))}")
        for output in (branch.get('observed_output') or {}).get('output', []):
            for content in output.get('content', []):
                if content.get('text'):
                    lines.append('PARTIAL / NOT COMPLETED: '+content['text'])


def render(folder, *, question_id=None, full=False):
    run, baseline, review, records = load_saved(folder)
    lines = [f"SAVED DAY 23 RUN: {run['eval_id']} | {run['created_at']}",
             f"Stages: retrieve={run['retrieve_status']}; compare={run['compare_status']}",
             f"BASELINE Day 22: {baseline['run']['eval_id']} | question hash: {run['question_hash']}",
             f"INDEX: {run['index']}",
             f"Top-N={run['config']['top_n']} | threshold={run['config']['threshold']:.2f} | max Top-K={run['config']['top_k']}",
             f"LIMITATION: {run['config']['limitation']}",
             f"FILTER ROLE: {run['config']['threshold_rationale']['filter_role']}",
             f"Baseline missing chunk ranks: {run['config']['threshold_rationale']['baseline_missing_chunk_ranks']}"]
    for mode in ('rewrite', 'embedding', 'enhanced'):
        phases = [r[mode] for r in records.values()]
        lines.append(f"{mode} calls attempted={sum(p['attempted'] for p in phases)}; "
                     f"statuses={dict(Counter(p['status'] for p in phases))}")
    if question_id is None:
        lines.extend(['', 'PER-FACT COMPARISON (manual labels; no total quality score)',
            'ID | rewrite intent/assumption | kept/below/K-limit | context22 | context23 | answer22 | answer23 | grounded23 | technical/review'])
        for q in run['questions']:
            r, item, b = records[q['id']], review['questions'][q['id']], baseline['records'][q['id']]
            bi = baseline['review']['questions'][q['id']]
            counts = Counter(c['decision'] for c in r['retrieval']['candidates'])
            rewrite = '/'.join(label(item[k], r['rewrite']['status']=='completed') for k in
                               ('rewrite_preserves_intent', 'rewrite_added_project_assumption'))
            cells = [fact_cell(bi, 'expected_fact_in_retrieved_context', b['retrieval']['status']=='completed'),
                     fact_cell(item, 'expected_fact_in_retrieved_context', r['retrieval']['status']=='completed'),
                     fact_cell(bi, 'rag_answer_covers_fact', b['rag']['status']=='completed'),
                     fact_cell(item, 'enhanced_answer_covers_fact', r['enhanced']['status']=='completed')]
            lines.append(' | '.join([q['id'], rewrite,
                '/'.join(str(counts[k]) for k in ('kept','dropped_below_threshold','dropped_top_k_limit')),
                *cells, grounded(item, r['enhanced']['status']=='completed'),
                '/'.join([r['retrieval']['status'],r['enhanced']['status'],item['status']])]))
        lines.append('Dropped counts are filter decisions, not proven irrelevant-chunk counts.')
        return '\n'.join(lines)
    q = next((q for q in run['questions'] if q['id']==question_id), None)
    if q is None:
        raise ValueError('Unknown question ID')
    r, item = records[question_id], review['questions'][question_id]
    b, bi = baseline['records'][question_id], baseline['review']['questions'][question_id]
    lines.extend(['', f"ORIGINAL QUESTION {question_id}: {r['original_question']}",
                  '', 'RETRIEVAL QUERY', r['retrieval_query'] or '[Unavailable]',
                  f"Rewrite technical status: {r['rewrite']['status']}",
                  '', 'TOP-10 BEFORE FILTERING'])
    for c in r['retrieval']['candidates']:
        lines.extend([f"rank={c['rank']} cosine={c['score']:.6f} | {c['source']}:{c['start_line']}-{c['end_line']}",
                      f"section: {c['section']} | chunk: {c['chunk_id']}",
                      c['text'] if full else c['text'][:350]+(' ... [--full]' if len(c['text'])>350 else '')])
    lines.extend(['', f"THRESHOLD {run['config']['threshold']:.2f} | KEPT/DROPPED"])
    for c in r['retrieval']['candidates']:
        lines.append(f"rank={c['rank']} cosine={c['score']:.6f}: {c['decision']}")
    lines.extend(['', f"FINAL CONTEXT (maximum Top-5) | {r['retrieval']['status']}"])
    if r['retrieval']['status']=='completed' and not r['retrieval']['final_context']:
        lines.append('0 chunks passing relevance criterion; empty context; no fallback.')
    for i,c in enumerate(r['retrieval']['final_context'],1):
        lines.append(f"[S{i}] candidate rank={c['rank']} | {c['source']}:{c['start_line']}-{c['end_line']} | {c['section']}")
    answer(lines, 'DAY 22 BASELINE ANSWER', b['rag'])
    answer(lines, 'DAY 23 ENHANCED ANSWER', r['enhanced'])
    lines.extend(['', 'EXPECTED FACTS / REVIEW', f"Reviewer: {review['reviewer']} | status: {item['status']}",
        f"rewrite_preserves_intent: {label(item['rewrite_preserves_intent'],r['rewrite']['status']=='completed')}",
        f"rewrite_added_project_assumption: {label(item['rewrite_added_project_assumption'],r['rewrite']['status']=='completed')}",
        item['rewrite_note']])
    for f in q['expected_facts']:
        v,bv=item['facts'][f['id']],bi['facts'][f['id']]
        cells=[label(bv['expected_fact_in_retrieved_context'],b['retrieval']['status']=='completed'),
               label(v['expected_fact_in_retrieved_context'],r['retrieval']['status']=='completed'),
               label(bv['rag_answer_covers_fact'],b['rag']['status']=='completed'),
               label(v['enhanced_answer_covers_fact'],r['enhanced']['status']=='completed')]
        lines.extend([f"{f['id']}: {f['text']}",f"  context22 / context23 / answer22 / answer23: {' / '.join(cells)}",
                      f"  Baseline review: {bv['notes']}",f"  Enhanced review: {v['notes']}"])
    for c in item['claims']:
        lines.append(f"Grounded={c['grounded_in_retrieved_context']}: {c['claim']} | {c.get('notes','')}")
    lines.extend([f"Diagnosis: {item['diagnosis']}",item['notes']])
    return '\n'.join(lines)
