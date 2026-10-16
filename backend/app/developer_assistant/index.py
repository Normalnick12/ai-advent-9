"""One Day 31 SQLite snapshot, explicit rebuild and read-only validation."""
import json
import os
import sqlite3
import tempfile
from contextlib import closing
from pathlib import Path

from app.document_indexing.chunking import chunk_source, config
from app.document_indexing.corpus import ROOT, Source, canonical, digest
from app.document_indexing.embedding import EMBEDDING_CONFIG
from app.first_rag.core import Index, vector_norm
from .corpus import MANIFEST, snapshot

DATABASE = ROOT / 'backend/.local/day31/index.sqlite3'
STRATEGY = 'structure-aware'


def metadata(snap):
    return dict(schema=1, manifest=snap.manifest, corpus_hash=snap.corpus_hash,
                chunking=config(), strategy=STRATEGY, embedding=dict(EMBEDDING_CONFIG))


def chunks(snap):
    return [c for source in snap.sources for c in chunk_source(source, STRATEGY)]


def safe_database(path):
    path = Path(path).absolute()
    for parent in (path, *path.parents):
        if parent.exists() or parent.is_symlink():
            info = parent.lstat()
            if parent.is_symlink() or parent.is_junction() or getattr(info, 'st_file_attributes', 0) & 0x400:
                raise ValueError('unsafe_index_path')
    return path


def read(path=DATABASE):
    try:
        path = safe_database(path)
        with closing(sqlite3.connect(path.as_uri() + '?mode=ro', uri=True)) as db:
            rows = db.execute('SELECT data FROM snapshot').fetchall()
        if len(rows) != 1:
            raise ValueError('invalid_index_rows')
        data = json.loads(rows[0][0])
        meta = data['metadata']
        sources = tuple(Source(**s) for s in data['sources'])
        from app.document_indexing.corpus import Snapshot
        snap = Snapshot(sources, meta['manifest'])
        if metadata(snap) != meta or not sources or len({s.source for s in sources}) != len(sources):
            raise ValueError('incompatible_index')
        expected = chunks(snap)
        actual = data['chunks']
        if not expected or len(expected) != len(actual):
            raise ValueError('invalid_chunks')
        norms = []
        for original, saved in zip(expected, actual, strict=True):
            if {k: v for k, v in saved.items() if k != 'embedding'} != original:
                raise ValueError('invalid_chunk_provenance')
            norms.append(vector_norm(saved['embedding']))
        provenance = {**meta, 'fingerprint': digest(canonical(meta)),
                      'chunk_count': len(actual), 'top_k': min(8, len(actual))}
        return Index(provenance, actual, norms, {s.source for s in sources})
    except (OSError, sqlite3.Error, KeyError, TypeError, json.JSONDecodeError):
        raise ValueError('index_missing_or_corrupt; run index') from None


def fresh(root=ROOT, manifest=MANIFEST, path=DATABASE):
    snap = snapshot(root, manifest)
    index = read(path)
    if any(index.provenance.get(k) != v for k, v in metadata(snap).items()):
        raise ValueError('index_stale; run index')
    return index


def build(embedder_factory, *, root=ROOT, manifest=MANIFEST, path=DATABASE, progress=lambda _: None):
    snap = snapshot(root, manifest)
    path = safe_database(path)
    if path.exists():
        try:
            index = fresh(root, manifest, path)
            return dict(status='unchanged', **index.provenance, embedding_calls=0, provider_tokens=0)
        except ValueError:
            pass  # Explicit index command is authorized to replace a stale/corrupt snapshot.
    selected = chunks(snap)
    if not selected:
        raise ValueError('empty_index')
    embedder, calls, usage = embedder_factory(), 0, 0
    try:
        for offset in range(0, len(selected), 32):
            batch = selected[offset:offset + 32]
            progress(f'embedding chunks {offset + 1}-{offset + len(batch)}/{len(selected)}')
            response = embedder.embed([c['text'] for c in batch])
            calls += 1
            if len(response.vectors) != len(batch):
                raise ValueError('embedding_count_mismatch')
            for c, vector in zip(batch, response.vectors, strict=True):
                vector_norm(vector)
                c['embedding'] = vector
            usage = usage + response.usage if usage is not None and response.usage is not None else None
    finally:
        embedder.close()
    if metadata(snapshot(root, manifest)) != metadata(snap):
        raise ValueError('corpus_changed_during_build')
    data = dict(metadata=metadata(snap), sources=[vars(s) for s in snap.sources], chunks=selected)
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix='index-', suffix='.sqlite3', dir=path.parent)
    os.close(descriptor)
    temporary = Path(temporary)
    try:
        with closing(sqlite3.connect(temporary)) as db, db:
            db.execute('CREATE TABLE snapshot (data TEXT NOT NULL)')
            db.execute('INSERT INTO snapshot VALUES (?)', (canonical(data),))
        index = read(temporary)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
    return dict(status='built', **index.provenance, embedding_calls=calls, provider_tokens=usage)
