"""Atomic SQLite snapshot; query connections are read-only."""
from contextlib import closing
from dataclasses import dataclass
import json
import sqlite3
import struct

from knowledge import canonical, changes, digest, index_path, policy, scan
from markdown_chunks import PROFILE, chunk_snapshot
from local_embeddings import check_profile, vector_norm


def fts_available():
    try:
        with closing(sqlite3.connect(":memory:")) as db:
            db.execute("CREATE VIRTUAL TABLE probe USING fts5(text)")
    except sqlite3.Error:
        raise RuntimeError("SQLite FTS5 недоступен в этой сборке Python.") from None


def connect(path, *, readonly=True):
    return sqlite3.connect(path.as_uri() + ("?mode=ro" if readonly else "?mode=rwc"), uri=True, timeout=2)


@dataclass
class Index:
    metadata: dict
    chunks: list

    @property
    def hashes(self):
        return self.metadata["sources"]


def read(root, *, required=True):
    fts_available()
    path = index_path(root)
    if not path.exists():
        if required:
            raise RuntimeError("Index отсутствует; выполните knowledge index.")
        return None
    try:
        with closing(connect(path)) as db:
            db.execute("BEGIN")
            meta = json.loads(db.execute("SELECT data FROM metadata WHERE id=1").fetchone()[0])
            if set(meta) != {"schema", "policy", "sources", "corpus_hash", "chunker", "embedding", "chunk_count"}:
                raise ValueError
            if type(meta["schema"]) is not int or meta["schema"] != 1 or meta["chunker"] != PROFILE:
                raise RuntimeError("Несовместимая версия index/chunker; нужен rebuild.")
            selection = meta["policy"]
            if (not isinstance(selection, dict) or set(selection) != {"includes", "excludes"}
                    or selection["includes"] is not None and not isinstance(selection["includes"], list)
                    or not isinstance(selection["excludes"], list)
                    or policy(includes=selection["includes"], excludes=selection["excludes"]) != selection):
                raise ValueError
            if not isinstance(meta["sources"], dict) or type(meta["chunk_count"]) is not int or not 1 <= meta["chunk_count"] <= 4096:
                raise ValueError
            check_profile(meta["embedding"])
            sources = dict(db.execute("SELECT path, hash FROM documents"))
            if sources != meta["sources"] or digest(canonical(sorted(sources.items()))) != meta["corpus_hash"]:
                raise ValueError
            if db.execute("PRAGMA foreign_key_check").fetchall():
                raise ValueError
            chunks = []
            dimension = meta["embedding"]["dimension"]
            for rowid, cid, source, data, raw in db.execute("SELECT rowid,id,source,data,vector FROM chunks ORDER BY rowid"):
                item = json.loads(data)
                if item["chunk_id"] != cid or item["source"] != source or source not in sources or digest(item["text"]) != item["text_hash"]:
                    raise ValueError
                vector = list(struct.unpack("<" + "f" * dimension, raw))
                vector_norm(vector, dimension)
                chunks.append({**item, "embedding": vector, "_rowid": rowid})
            if not chunks or len(chunks) != meta["chunk_count"] or len({c["chunk_id"] for c in chunks}) != len(chunks):
                raise ValueError
            fts = list(db.execute("SELECT rowid,section,text FROM chunks_fts ORDER BY rowid"))
            if fts != [(c["_rowid"], c["section"], c["text"]) for c in chunks]:
                raise ValueError
            return Index(meta, chunks)
    except (sqlite3.Error, ValueError, KeyError, TypeError, IndexError, AttributeError, struct.error, OverflowError):
        raise RuntimeError("Index повреждён или несовместим; требуется rebuild.") from None


def fresh(root, index):
    snapshot = scan(root, index.metadata["policy"])
    diff = changes(snapshot, index.hashes)
    if any(diff[k] for k in ("added", "deleted", "changed")):
        raise RuntimeError("Index устарел; выполните knowledge index.")
    actual = [{k: v for k, v in c.items() if k not in {"embedding", "_rowid"}} for c in index.chunks]
    if chunk_snapshot(snapshot) != actual:
        raise RuntimeError("Index provenance не соответствует Knowledge; нужен rebuild.")
    return snapshot


def write(root, snapshot, profile, chunks, vectors, *, before_commit=None):
    check_profile(profile)
    if not chunks or len(chunks) != len(vectors):
        raise RuntimeError("Chunk/vector count mismatch.")
    if chunks != chunk_snapshot(snapshot):
        raise RuntimeError("Chunk provenance не соответствует snapshot.")
    packed = []
    for vector in vectors:
        vector_norm(vector, profile["dimension"])
        try:
            raw = struct.pack("<" + "f" * profile["dimension"], *vector)
        except (struct.error, OverflowError):
            raise RuntimeError("Embedding не представим как float32.") from None
        vector_norm(list(struct.unpack("<" + "f" * profile["dimension"], raw)), profile["dimension"])
        packed.append(raw)
    selection = dict(snapshot.policy)
    if selection["includes"] is not None:
        selection["includes"] = sorted(snapshot.sources)
    meta = {"schema": 1, "policy": selection, "sources": snapshot.hashes,
            "corpus_hash": snapshot.corpus_hash, "chunker": PROFILE,
            "embedding": profile, "chunk_count": len(chunks)}
    fts_available()
    path = index_path(root)
    path.parent.mkdir(exist_ok=True)
    path = index_path(root)
    try:
        with closing(connect(path, readonly=False)) as db:
            db.execute("PRAGMA foreign_keys=ON")
            db.execute("BEGIN IMMEDIATE")
            try:
                db.execute("CREATE TABLE IF NOT EXISTS metadata(id INTEGER PRIMARY KEY CHECK(id=1),data TEXT NOT NULL)")
                db.execute("CREATE TABLE IF NOT EXISTS documents(path TEXT PRIMARY KEY,hash TEXT NOT NULL)")
                db.execute("CREATE TABLE IF NOT EXISTS chunks(id TEXT PRIMARY KEY,source TEXT REFERENCES documents(path),data TEXT NOT NULL,vector BLOB NOT NULL)")
                db.execute("CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(section,text,tokenize=\"unicode61 tokenchars '_'\")")
                for table in ("chunks_fts", "chunks", "documents", "metadata"):
                    db.execute("DELETE FROM " + table)
                db.executemany("INSERT INTO documents VALUES(?,?)", sorted(snapshot.hashes.items()))
                db.execute("INSERT INTO metadata VALUES(1,?)", (canonical(meta),))
                for number, (chunk, vector) in enumerate(zip(chunks, packed), 1):
                    db.execute("INSERT INTO chunks(rowid,id,source,data,vector) VALUES(?,?,?,?,?)",
                               (number, chunk["chunk_id"], chunk["source"], canonical(chunk), vector))
                    db.execute("INSERT INTO chunks_fts(rowid,section,text) VALUES(?,?,?)",
                               (number, chunk["section"], chunk["text"]))
                if before_commit:
                    before_commit()
                if scan(root, snapshot.policy).hashes != snapshot.hashes:
                    raise RuntimeError("Knowledge изменён во время индексации; index не опубликован.")
                db.commit()
            except BaseException:
                db.rollback()
                raise
    except sqlite3.Error:
        raise RuntimeError("Не удалось атомарно записать index (SQLite/busy/disk).") from None
