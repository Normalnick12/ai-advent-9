from dataclasses import asdict
from hashlib import sha256
from pathlib import Path

from app.document_indexing.corpus import canonical, digest
from app.first_rag.core import CONFIG, CORPUS_HASH, RUN_ID, STRATEGY, question_set
from app.first_rag.report import load_report
from app.llm_client import AgentConfig

BASELINE_ID = "f7b78426-9672-437f-ab93-717a826934da"
TOP_N, TOP_K, THRESHOLD = 10, 5, 0.50
REWRITE_CONFIG = AgentConfig(
    instructions=(
        "Преобразуй исходный вопрос в один компактный поисковый запрос для retrieval "
        "по документации и коду проекта. Верни только запрос, без ответа и пояснений. "
        "Сохрани смысл, все условия и отрицания, Day и предметную область, точные "
        "identifiers и endpoints. Если вопрос касается нескольких сторон, например "
        "backend и UI, сохрани обе. Не добавляй предполагаемые проектные правила, "
        "ответы, имена классов или методы, которых нет в исходном вопросе."
    ), max_output_tokens=250, truncation="disabled", version="day23-rewrite-v1",
)
LIMITATION = (
    "Threshold 0.50 выбран по Day 22 questions/evidence, включая Q10, на original queries. "
    "Rewrite изменяет embeddings/scores; comparison не является независимым benchmark. "
    "Cosine не вероятность релевантности. Порог и rewrite prompt после live не меняются."
)
RATIONALE = {
    "grid": [0.40, 0.45, 0.50, 0.55, 0.60],
    "selection": "Минимальный порог сетки, обнуляющий original Q10 и оставляющий hit всем positive questions.",
    "original_q10_max": 0.4943461840748868,
    "original_top5_retained": [4, 1, 3, 2, 3, 5, 5, 5, 5, 0],
    "baseline_missing_chunk_ranks": {"Q07": [20, 32], "Q08": [74]},
    "filter_role": "Filter не меняет cosine ranking; Top-10 служит наблюдаемости. Возможное исправление поиска — rewrite.",
}


def experiment_config():
    return dict(top_n=TOP_N, top_k=TOP_K, threshold=THRESHOLD,
                rewrite=asdict(REWRITE_CONFIG), generation=asdict(CONFIG),
                limitation=LIMITATION, threshold_rationale=RATIONALE)


def load_baseline(folder, index):
    folder = Path(folder)
    run, review, records = load_report(folder)
    frozen, fingerprint = question_set(source_paths=index.sources)
    if (run['eval_id'] != BASELINE_ID or run['command'] != 'eval'
            or run['index'] != index.provenance
            or index.provenance['run_id'] != RUN_ID
            or index.provenance['corpus_hash'] != CORPUS_HASH
            or index.provenance['strategy'] != STRATEGY
            or index.provenance['chunk_count'] != 226
            or run['config'] != asdict(CONFIG)
            or run['question_hash'] != fingerprint
            or run['frozen_question_set'] != frozen or run['questions'] != frozen['questions']):
        raise ValueError('Incompatible pinned baseline')
    for q in run['questions']:
        r = records[q['id']]
        if r is None or r['id'] != q['id'] or r['question'] != q['question']:
            raise ValueError('Invalid baseline question checkpoint')
        for mode in ('direct', 'rag'):
            if r[mode]['attempted'] and r[mode]['config'] != run['config']:
                raise ValueError('Incompatible baseline branch config')
    hashes = {p.name: sha256(p.read_bytes()).hexdigest() for p in
              [folder/'run.json', folder/'review.json', *[folder/f"{q['id']}.json" for q in run['questions']]]}
    return dict(run=run, review=review, records=records,
                provenance=dict(eval_id=run['eval_id'], file_hashes=hashes))


def select(candidates):
    kept, decisions = [], []
    for c in candidates:
        reason = ('dropped_below_threshold' if c['score'] < THRESHOLD else
                  'dropped_top_k_limit' if len(kept) == TOP_K else 'kept')
        decisions.append({**c, 'decision': reason})
        if reason == 'kept':
            kept.append(c)
    return decisions, kept


def retrieval_hash(records):
    return digest(canonical([{k: v for k, v in r.items() if k != 'enhanced'}
                             for r in records.values()]))
