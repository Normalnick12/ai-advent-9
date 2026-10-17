"""FAQ snapshot in RAM; all synchronous provider work runs in a worker thread."""
import asyncio
from dataclasses import dataclass
from pathlib import Path

from app.document_indexing.chunking import chunk_source, config
from app.document_indexing.corpus import ROOT, canonical, digest, load_corpus
from app.document_indexing.embedding import EMBEDDING_CONFIG, OpenAIEmbedder
from app.first_rag.core import Index, search, vector_norm

MANIFEST = ROOT / 'day-33-support-assistant/corpus.json'
FAQ_FILES = {'login', 'temporary-lock', 'expired-code', 'login-diagnostics', 'delivery'}


def embed_once(factory, texts):
    # Construction, HTTP call and disposal all belong to the worker, never the event loop.
    embedder = factory()
    try:
        result = embedder.embed(texts)
        if len(result.vectors) != len(texts):
            raise ValueError('embedding_count_mismatch')
        for vector in result.vectors:
            vector_norm(vector)
        return result
    finally:
        embedder.close()


@dataclass
class FaqIndex:
    index: Index
    documents: dict
    startup: dict


def build(factory=OpenAIEmbedder, *, root=ROOT, manifest=MANIFEST):
    snapshot = load_corpus(Path(root), Path(manifest))
    expected = {f'day-33-support-assistant/faq/{name}.md' for name in FAQ_FILES}
    if {s.source for s in snapshot.sources} != expected:
        raise ValueError('unexpected_faq_manifest')
    chunks = [c for s in snapshot.sources for c in chunk_source(s, 'structure-aware')]
    result = embed_once(factory, [c['text'] for c in chunks])
    for chunk, vector in zip(chunks, result.vectors, strict=True):
        chunk['embedding'] = vector
    fingerprint = digest(canonical(dict(corpus_hash=snapshot.corpus_hash, chunking=config(),
                                        embedding=EMBEDDING_CONFIG)))
    index = Index(dict(fingerprint=fingerprint), chunks, [vector_norm(c['embedding']) for c in chunks], expected)
    documents = {Path(s.source).stem: dict(source=s.source, text=s.text) for s in snapshot.sources}
    return FaqIndex(index, documents, dict(embedding_calls=1, embedding_tokens=result.usage,
                                          documents=len(documents), chunks=len(chunks)))


async def build_async(factory=OpenAIEmbedder, **options):
    return await asyncio.to_thread(build, factory, **options)


async def retrieve(faq, question, observations, factory=OpenAIEmbedder):
    known = [f'{name}={getattr(observations, name)}' for name in
             ('error_code', 'account_status', 'verification_status') if getattr(observations, name) is not None]
    query = '\n'.join([question, *known])
    result = await asyncio.to_thread(embed_once, factory, [query])
    hits = search(faq.index, result.vectors[0], top_k=min(2, len(faq.index.chunks)))
    fields = ('chunk_id', 'source', 'section', 'start_line', 'end_line', 'text')
    context = [dict(label=f'[S{i}]', **{k: hit[k] for k in fields}) for i, hit in enumerate(hits, 1)]
    trace = dict(status='completed', fingerprint=faq.index.provenance['fingerprint'],
                 embedding_calls=1, embedding_tokens=result.usage,
                 hits=[{k: hit[k] for k in ('source', 'chunk_id', 'score', 'rank')} for hit in hits])
    return context, trace
