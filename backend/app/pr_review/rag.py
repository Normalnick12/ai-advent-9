"""Small per-run corpus: Day 31 docs, changed code, at most two obvious tests."""
import json
from pathlib import PurePosixPath

from app.document_indexing.chunking import chunk_source, fitting_length, token_count
from app.document_indexing.corpus import ROOT, Source, canonical, digest
from app.first_rag.core import Index, search, vector_norm

from . import (MAX_CHUNKS, MAX_CORPUS_BYTES, MAX_DIFF_TOKENS, MAX_SOURCES,
               ReviewError, require)

DOCS = ('README.md', 'docs/project-structure.md', 'backend/README.md',
        'android-app/README.md', 'scripts/README.md')
TESTS = {
    'first_rag': ('test_first_rag.py',),
    'document_indexing': ('test_document_indexing.py',),
    'grounded_rag': ('test_grounded_rag.py',),
}


def related_tests(path):
    p = PurePosixPath(path)
    if path.startswith('backend/app/') and p.suffix == '.py':
        group = path.split('/')[2]
        if group == 'developer_assistant':
            names = (('test_day31_index.py',) if p.stem in {'index', 'corpus'} else
                     ('test_day31_mcp.py',) if p.stem in {'mcp_client', 'git_mcp_server'} else
                     ('test_day31_help.py',))
        else:
            names = TESTS.get(group, (f'test_{p.stem}.py',))
        return ['backend/tests/' + name for name in names][:2]
    if p.suffix == '.kt' and '/src/main/' in path:
        return [path.replace('/src/main/', f'/src/{kind}/').removesuffix('.kt') + 'Test.kt'
                for kind in ('test', 'androidTest')]
    return []


def prepare(gh, snap, *, manifest=ROOT / 'day-31-developer-assistant/corpus.json'):
    require(token_count(snap.diff) <= MAX_DIFF_TOKENS, 'too_large', 'diff_tokens_limit')
    data = json.loads(manifest.read_text(encoding='utf-8-sig'))
    require(data == {'sources': [{'source': p, 'source_type': 'documentation'} for p in DOCS]},
            'configuration_error', 'unexpected_docs_manifest')
    sources, missing, seen = [], [], set()

    def add(path, revision, kind, *, optional=False):
        key = path, revision
        if key in seen:
            return
        text = gh.file(path, revision, optional=optional)
        if text is None:
            missing.append(path)
            return
        seen.add(key)
        sources.append(dict(path=path, revision=revision, kind=kind, text=text))
        require(len(sources) <= MAX_SOURCES and
                sum(len(s['text'].encode('utf-8')) for s in sources) <= MAX_CORPUS_BYTES,
                'too_large', 'corpus_size_limit')

    for path in DOCS:
        add(path, snap.base, 'documentation')
    queries = []
    for f in snap.files:
        if PurePosixPath(f['path']).suffix not in {'.py', '.kt'}:
            continue
        removed = f['status'] == 'removed'
        path, revision = (f['old_path'], snap.merge_base) if removed else (f['path'], snap.head)
        add(path, revision, 'code')
        for candidate in related_tests(path):
            add(candidate, revision, 'code', optional=True)
        query = path + '\n' + f['patch']
        queries.append(query[:fitting_length(len(query), lambda n: query[:n], 512)])
    require(queries, 'insufficient_context', 'no_changed_source_code')
    groups = {'documentation': [], 'code': []}
    for s in sources:
        kind = 'documentation' if s['kind'] == 'documentation' else 'backend' if s['path'].endswith('.py') else 'android'
        for chunk in chunk_source(Source(s['path'], kind, s['text']), 'structure-aware'):
            chunk.update(path=s['path'], revision=s['revision'], kind=s['kind'],
                         chunk_id=digest(canonical([chunk['chunk_id'], s['revision']])))
            groups[s['kind']].append(chunk)
    require(all(groups.values()), 'insufficient_context', 'empty_context_group')
    require(sum(map(len, groups.values())) <= MAX_CHUNKS, 'too_large', 'chunk_count_limit')
    return groups, queries, dict(source_count=len(sources), chunk_count=sum(map(len, groups.values())),
                                missing_tests=sorted(set(missing)))


def retrieve(groups, queries, embedder):
    chunks = groups['documentation'] + groups['code']
    calls, usage = 0, 0

    def embed(texts):
        nonlocal calls, usage
        calls += 1
        response = embedder.embed(texts)
        require(len(response.vectors) == len(texts), 'provider_error', 'embedding_count_mismatch')
        for vector in response.vectors:
            vector_norm(vector)
        usage = usage + response.usage if usage is not None and response.usage is not None else None
        return response.vectors

    try:
        for offset in range(0, len(chunks), 32):
            batch = chunks[offset:offset + 32]
            for chunk, vector in zip(batch, embed([c['text'] for c in batch]), strict=True):
                chunk['embedding'] = vector
        vectors = embed(queries)
        selected = {}
        for kind, group in groups.items():
            idx = Index({}, group, [vector_norm(c['embedding']) for c in group], {c['source'] for c in group})
            best = {}
            for vector in vectors:
                for hit in search(idx, vector, top_k=min(6, len(group))):
                    previous = best.get(hit['chunk_id'])
                    if previous is None or hit['score'] > previous['score']:
                        best[hit['chunk_id']] = hit
            hits = sorted(best.values(), key=lambda h: (-h['score'], h['source'], h['ordinal'], h['chunk_id']))[:6]
            selected[kind] = [dict(id=('S' if kind == 'documentation' else 'C') + str(i),
                **{k: h[k] for k in ('path', 'revision', 'start_line', 'end_line', 'text', 'kind')})
                for i, h in enumerate(hits, 1)]
    except ReviewError:
        raise
    except (ValueError, TypeError):
        raise ReviewError('provider_error', 'embedding_failed') from None
    return selected, dict(embedding_calls=calls, embedding_tokens=usage)
