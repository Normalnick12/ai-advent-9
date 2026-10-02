"""Compact, read-only presentation of saved evidence and manual labels."""
from collections import Counter
import re
from textwrap import fill, shorten

from .experiment import load_saved
from .report import label

WIDTH = 100
FIELDS = {'context': ('expected_fact_in_retrieved_context', 'expected_fact_in_retrieved_context'),
          'answer': ('rag_answer_covers_fact', 'enhanced_answer_covers_fact')}


def coverage(record, baseline_record, item, baseline_item):
    pairs = {}
    for name, (old_field, new_field) in FIELDS.items():
        old_available = baseline_record['retrieval' if name == 'context' else 'rag']['status'] == 'completed'
        new_available = record['retrieval' if name == 'context' else 'enhanced']['status'] == 'completed'
        pairs[name] = {fid: (label(baseline_item['facts'][fid][old_field], old_available),
                             label(fact[new_field], new_available)) for fid, fact in item['facts'].items()}
    return pairs


def verdict(pairs, reviewed):
    order = ('no', 'partial', 'yes')
    changes = [order.index(new) - order.index(old) for group in pairs.values()
               for old, new in group.values() if old in order and new in order]
    complete = reviewed and all(old in order and new in order for group in pairs.values()
                               for old, new in group.values())
    if not complete:
        return 'PENDING / UNAVAILABLE'
    worse, better = any(c < 0 for c in changes), any(c > 0 for c in changes)
    return ('MIXED' if worse and better else 'REGRESSION' if worse else
            'IMPROVEMENT' if better else 'NO CHANGE')


def reviewed_candidates(item):
    """Use explicit candidate/rank references in fact notes; never infer relevance."""
    refs = {}
    for fid, fact in item['facts'].items():
        for match in re.finditer(r'\b(?:candidate\s+|rank\s*=\s*)(\d+)\b', fact['notes'], re.IGNORECASE):
            refs.setdefault(int(match[1]), set()).add(fid)
    return refs


def brief(text, width=WIDTH):
    return shorten(' '.join(text.split()), width=width, placeholder=' ...')


def render_video(folder, *, question_id=None):
    run, baseline, review, records = load_saved(folder)
    config = run['config']
    lines = [f"SAVED RUN: {run['eval_id']}" + (f' | {question_id}' if question_id else ''),
             f"PIPELINE: rewrite → Top-{config['top_n']} → threshold {config['threshold']:.2f} "
             f"→ Top-{config['top_k']} (maximum)"]
    comparisons = {q['id']: coverage(records[q['id']], baseline['records'][q['id']],
                                    review['questions'][q['id']], baseline['review']['questions'][q['id']])
                   for q in run['questions']}
    verdicts = {qid: verdict(pairs, review['questions'][qid]['status'] == 'reviewed')
                for qid, pairs in comparisons.items()}
    if question_id is None:
        lines.append(f"STAGES: retrieve={run['retrieve_status']}; compare={run['compare_status']}")
        lines.append('PROVIDER CALLS / STATUS (saved dispatches):')
        for mode in ('rewrite', 'embedding', 'enhanced'):
            phases = [r[mode] for r in records.values()]
            statuses = ', '.join(f'{n} {status}' for status, n in Counter(p['status'] for p in phases).items())
            lines.append(f"  {mode}: {sum(p['attempted'] for p in phases)} attempted | {statuses}")
        lines.extend(['', 'RESULT: per-fact context + answer changes from saved manual review; no total score.'])
        for category in ('REGRESSION', 'IMPROVEMENT', 'NO CHANGE', 'MIXED', 'PENDING / UNAVAILABLE'):
            ids = [qid for qid, value in verdicts.items() if value == category]
            if ids or category in {'REGRESSION', 'IMPROVEMENT', 'NO CHANGE'}:
                lines.append(f"{category}: {', '.join(ids) or 'none'}")
        for qid, value in verdicts.items():
            if value in {'REGRESSION', 'MIXED'}:
                lost = []
                for name, group in comparisons[qid].items():
                    by_change = {}
                    for fid, (old, new) in group.items():
                        if old in {'yes', 'partial'} and new in {'partial', 'no'} and old != new:
                            by_change.setdefault((old, new), []).append(fid)
                    lost.extend(f"{name} {','.join(ids)}: {old} → {new}"
                                for (old, new), ids in by_change.items())
                lines.append(fill(f"! {qid} {value}: " + '; '.join(lost), width=WIDTH))
        unsupported = {qid: sum(c['grounded_in_retrieved_context'] == 'no' for c in item['claims'])
                       for qid, item in review['questions'].items()}
        lines.append('UNSUPPORTED ENHANCED CLAIMS: ' +
                     (', '.join(f'{qid}: {n}' for qid, n in unsupported.items() if n) or 'none in saved review'))
        lines.extend(['', fill('LIMITATION: ' + config['limitation'], width=WIDTH),
                      'Details: --question Qxx --video | full evidence: omit --video.'])
        return '\n'.join(lines)

    q = next((q for q in run['questions'] if q['id'] == question_id), None)
    if q is None:
        raise ValueError('Unknown question ID')
    record, item = records[question_id], review['questions'][question_id]
    pairs = comparisons[question_id]
    refs = reviewed_candidates(item)
    candidates = record['retrieval']['candidates']
    selected = [c for c in candidates if c['decision'] == 'kept' or c['rank'] in refs]
    lines.extend(['', '1. QUESTION', fill(record['original_question'], width=WIDTH),
                  '', '2. REWRITE', fill(record['retrieval_query'] or '[Unavailable]', width=WIDTH),
                  f"status={record['rewrite']['status']} | intent={item['rewrite_preserves_intent'] or 'pending'} "
                  f"| added assumption={item['rewrite_added_project_assumption'] or 'pending'}",
                  '', '3. IMPORTANT CANDIDATES (kept + explicit fact-review references)'])
    for c in selected:
        reason = c['decision'].removeprefix('dropped_')
        reference = f" | review {','.join(sorted(refs[c['rank']]))}" if c['rank'] in refs else ''
        title = c['section'].rsplit(' / ', 1)[-1].removeprefix('Requirement: ').removeprefix('Scenario: ')
        source_parts = c['source'].split('/')
        source = source_parts[-2] if source_parts[-1] in {'spec.md', 'README.md'} and len(source_parts) > 1 else source_parts[-1]
        lines.append(brief(f"r{c['rank']:02}  {c['score']:.4f}  {reason}{reference} | {source}: {title}"))
    if not selected:
        lines.append('[No available candidates]')
    counts = Counter(c['decision'].removeprefix('dropped_') for c in candidates)
    lines.append(f"Decisions: kept={counts['kept']}; below_threshold={counts['below_threshold']}; "
                 f"top_k_limit={counts['top_k_limit']}. Other dropped candidates omitted.")
    kept = record['retrieval']['final_context']
    lines.extend(['', f"4. FINAL CONTEXT | {record['retrieval']['status']}",
                  (' | '.join(f"[S{i}] ← r{c['rank']:02}" for i, c in enumerate(kept, 1)) or '[Empty; no fallback]')
                  if record['retrieval']['status'] == 'completed' else '[Unavailable]',
                  '', '5. BASELINE vs ENHANCED FACT COVERAGE (final context)'])
    for fact in q['expected_facts']:
        old, new = pairs['context'][fact['id']]
        lines.append(brief(f"{fact['id']}: {old} → {new} | {fact['text']}"))
    lines.extend(['', '6. BASELINE vs ENHANCED ANSWER COVERAGE',
                  ' | '.join(f'{fid}: {old} → {new}' for fid, (old, new) in pairs['answer'].items()),
                  '', '7. TAKEAWAY', f"{verdicts[question_id]} | saved review: {item['status']}"])
    for c in selected:
        if c['decision'] != 'kept' and c['rank'] in refs:
            relation = '<' if c['decision'] == 'dropped_below_threshold' else '>='
            lines.append(f"Review {','.join(sorted(refs[c['rank']]))}: r{c['rank']} score {c['score']:.4f} "
                         f"{relation} {config['threshold']:.2f}; {c['decision'].removeprefix('dropped_')}; absent from context.")
    absent = [fid for fid, (_, new) in pairs['context'].items() if new == 'no']
    if kept and absent:
        lines.append(f"{len(kept)} chunks passed the filter; saved review still finds no context evidence for {','.join(absent)}.")
    for fid, fact in item['facts'].items():
        if fact['expected_fact_in_retrieved_context'] in {'no', 'partial'} and fact['notes']:
            first_sentence = re.split(r'(?<=[.!?])\s+', fact['notes'])[0]
            lines.append(fill(f'Saved review {fid}: ' + brief(first_sentence, 170), width=WIDTH))
            break
    unsupported = sum(c['grounded_in_retrieved_context'] == 'no' for c in item['claims'])
    lines.append(f"Enhanced unsupported claims: {unsupported} | rewrite/embedding/enhanced: "
                 + '/'.join(record[k]['status'] for k in ('rewrite', 'embedding', 'enhanced')))
    return '\n'.join(lines)
