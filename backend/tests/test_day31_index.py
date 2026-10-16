import json
import os
import sqlite3
from pathlib import Path
from unittest.mock import Mock

import pytest

from app.developer_assistant import corpus, index
from app.document_indexing.embedding import DIMENSION, Embeddings
from app.first_rag.core import search


def vector(x=1, y=0):
    return [float(x), float(y)] + [0.] * (DIMENSION - 2)


class Embedder:
    def __init__(self, callback=None):
        self.calls, self.closed, self.callback = [], False, callback

    def embed(self, texts):
        self.calls.append(texts)
        if self.callback:
            self.callback()
        return Embeddings([vector() for _ in texts], len(texts))

    def close(self):
        self.closed = True


@pytest.fixture
def project(tmp_path):
    (tmp_path / 'README.md').write_text('# Проект\n\nBackend отвечает Android.\n', encoding='utf8')
    manifest = tmp_path / 'corpus.json'
    manifest.write_text(json.dumps({'sources': [{'source': 'README.md', 'source_type': 'documentation'}]}))
    return dict(root=tmp_path, manifest=manifest, path=tmp_path / '.local/index.sqlite3')


def test_real_five_file_corpus():
    snap = corpus.snapshot()
    assert {s.source for s in snap.sources} == corpus.READMES | {'docs/project-structure.md'}
    assert len(snap.sources) == 5


@pytest.mark.parametrize('name', ['../README.md', '/README.md', 'C:/README.md', 'docs/../README.md',
                                    'docs/.env.md', 'docs//a.md', 'backend/app/main.py', 'openspec/specs/x.md'])
def test_invalid_selection(project, name):
    project['manifest'].write_text(json.dumps({'sources': [{'source': name, 'source_type': 'documentation'}]}))
    with pytest.raises(ValueError):
        corpus.snapshot(project['root'], project['manifest'])


def test_duplicates_missing_encoding_size_and_no_crawl(project, monkeypatch):
    root, manifest = project['root'], project['manifest']
    entry = {'source': 'README.md', 'source_type': 'documentation'}
    manifest.write_text(json.dumps({'sources': [entry, entry]}))
    with pytest.raises(ValueError):
        corpus.snapshot(root, manifest)
    manifest.write_text(json.dumps({'sources': [entry]}))
    (root / 'README.md').write_text('[other](docs/absent.md)\n', encoding='utf8')
    assert len(corpus.snapshot(root, manifest).sources) == 1
    monkeypatch.setattr(corpus, 'MAX_DOC', 2)
    with pytest.raises(ValueError, match='size'):
        corpus.snapshot(root, manifest)
    monkeypatch.undo()
    (root / 'README.md').write_bytes(b'\xff')
    with pytest.raises(ValueError):
        corpus.snapshot(root, manifest)
    (root / 'README.md').unlink()
    with pytest.raises(ValueError):
        corpus.snapshot(root, manifest)


def test_reparse_and_total_limits(project, monkeypatch):
    original = Path.is_junction
    monkeypatch.setattr(Path, 'is_junction', lambda p: p.name == 'README.md' or original(p))
    with pytest.raises(ValueError, match='unsafe'):
        corpus.snapshot(project['root'], project['manifest'])
    monkeypatch.undo()
    monkeypatch.setattr(corpus, 'MAX_TOTAL', 2)
    with pytest.raises(ValueError, match='size'):
        corpus.snapshot(project['root'], project['manifest'])


def test_roundtrip_small_index_noop_and_freshness(project):
    e = Embedder()
    result = index.build(lambda: e, **project)
    assert result['status'] == 'built' and e.closed and len(e.calls) == 1
    saved = index.fresh(**project)
    assert len(saved.chunks) == 1
    factory = Mock(side_effect=AssertionError('no provider call'))
    assert index.build(factory, **project)['status'] == 'unchanged'
    assert search(saved, vector(), top_k=1)[0]['source'] == 'README.md'
    (project['root'] / 'excluded.md').write_text('not indexed')
    index.fresh(**project)
    original = (project['root'] / 'README.md').read_bytes().replace(b'\r\n', b'\n')
    (project['root'] / 'README.md').write_bytes(b'\xef\xbb\xbf' + original.replace(b'\n', b'\r\n'))
    index.fresh(**project)
    (project['root'] / 'README.md').write_text('changed')
    with pytest.raises(ValueError, match='stale'):
        index.fresh(**project)


def test_manifest_change_and_config(project, monkeypatch):
    index.build(Embedder, **project)
    (project['root'] / 'docs').mkdir()
    (project['root'] / 'docs/a.md').write_text('# A\nNew docs')
    manifest = json.loads(project['manifest'].read_text())
    manifest['sources'].append({'source': 'docs/a.md', 'source_type': 'documentation'})
    project['manifest'].write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match='stale'):
        index.fresh(**project)
    index.build(Embedder, **project)
    monkeypatch.setattr(index, 'STRATEGY', 'fixed-size')
    with pytest.raises(ValueError):
        index.fresh(**project)


@pytest.mark.parametrize('mode', ['embedding', 'replace', 'write', 'changed'])
def test_failed_rebuild_preserves_previous(project, monkeypatch, mode):
    index.build(Embedder, **project)
    previous = project['path'].read_bytes()
    doc = project['root'] / 'README.md'
    doc.write_text('# Changed\nNew content')
    e = Embedder()
    if mode == 'embedding':
        e.embed = Mock(return_value=Embeddings([vector()[:-1]], 1))
    elif mode == 'replace':
        monkeypatch.setattr(os, 'replace', Mock(side_effect=OSError('private')))
    elif mode == 'write':
        monkeypatch.setattr(index.tempfile, 'mkstemp', Mock(side_effect=OSError('private')))
    else:
        e.callback = lambda: doc.write_text('changed during embedding')
    with pytest.raises((ValueError, OSError)):
        index.build(lambda: e, **project)
    assert project['path'].read_bytes() == previous and e.closed


@pytest.mark.parametrize('field', ['vector', 'text', 'hash', 'metadata', 'rows'])
def test_corruption_rejected(project, field):
    index.build(Embedder, **project)
    with sqlite3.connect(project['path']) as db:
        data = json.loads(db.execute('SELECT data FROM snapshot').fetchone()[0])
        if field == 'vector':
            data['chunks'][0]['embedding'][0] = float('nan')
        elif field == 'text':
            data['chunks'][0]['text'] = 'forged'
        elif field == 'hash':
            data['chunks'][0]['chunk_id'] = 'wrong'
        elif field == 'metadata':
            data['metadata']['embedding']['dimension'] = 2
        else:
            db.execute('INSERT INTO snapshot VALUES (?)', (json.dumps(data),))
        db.execute('UPDATE snapshot SET data=?', (json.dumps(data),))
    with pytest.raises(ValueError):
        index.fresh(**project)


def test_batches_and_unicode_slices(project):
    text = '# Unicode\n' + ('Очень длинный абзац 🦊. ' * 3000)
    (project['root'] / 'README.md').write_text(text, encoding='utf8')
    e = Embedder()
    index.build(lambda: e, **project)
    saved = index.read(project['path'])
    assert len(e.calls) > 1 and all(len(batch) <= 32 for batch in e.calls)
    for c in saved.chunks:
        assert text[c['start_char']:c['end_char']] == c['text']
        assert c['token_count'] <= 500
    hits = search(saved, vector(), top_k=min(8, len(saved.chunks)))
    assert [h['ordinal'] for h in hits] == sorted(h['ordinal'] for h in hits)
