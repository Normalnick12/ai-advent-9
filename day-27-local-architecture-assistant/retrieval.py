"""Two independent rankings on the same approved snapshot."""
from contextlib import closing
import math
from pathlib import PurePosixPath
import re
import sqlite3

from knowledge import canonical, index_path
from knowledge_index import connect
from local_embeddings import vector_norm


def query_text(question, filename=None):
    if not isinstance(question, str) or not question.strip() or len(question) > 2000:
        raise ValueError("Нужен непустой query до 2000 символов.")
    result = question
    if filename:
        stem = PurePosixPath(filename.replace("\\", "/")).stem
        words = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1 \2", stem)
        words = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", words).split()
        extra = list(dict.fromkeys([stem, *words]))
        result += "\n" + " ".join(extra)
    if len(result) > 4096:
        raise ValueError("Enriched query превышает 4096 символов.")
    return result


def terms(query):
    # MATCH syntax/operators are always quoted literal tokens, never executable SQL.
    values = list(dict.fromkeys(re.findall(r"\w+", query, re.UNICODE)))
    if len(values) > 64:
        raise ValueError("Text query превышает 64 literal terms.")
    return " OR ".join('"' + value + '"' for value in values)


def search(root, index, query, mode, top_k=4, vector=None):
    if type(top_k) is not int or not 1 <= top_k <= 10:
        raise ValueError("top-k должен быть 1..10.")
    hits = []
    if mode == "text":
        expression = terms(query)
        if not expression:
            return []
        try:
            with closing(connect(index_path(root))) as db:
                db.execute("BEGIN")
                if db.execute("SELECT data FROM metadata WHERE id=1").fetchone()[0] != canonical(index.metadata):
                    raise RuntimeError("Index изменился во время поиска; повторите команду явно.")
                # Rank all matching rows (bounded by 4096) for deterministic ties.
                scores = dict(db.execute("SELECT rowid,bm25(chunks_fts) FROM chunks_fts WHERE chunks_fts MATCH ?", (expression,)))
        except sqlite3.Error:
            raise RuntimeError("Ошибка FTS5; поиск не выполнен.") from None
        hits = [(scores[c["_rowid"]], c) for c in index.chunks if c["_rowid"] in scores]
    elif mode == "vector":
        dim = index.metadata["embedding"]["dimension"]
        norm = vector_norm(vector, dim)
        # Adapted from Week 5 cosine search, with the local profile's dimension.
        for c in index.chunks:
            v = c["embedding"]
            other_norm = vector_norm(v, dim)
            score = math.fsum((a / norm) * (b / other_norm) for a, b in zip(vector, v))
            hits.append((-score, c))
    else:
        raise ValueError("Неизвестный search mode.")
    hits.sort(key=lambda pair: (pair[0], pair[1]["source"], pair[1]["ordinal"], pair[1]["chunk_id"]))
    return [{**{k: v for k, v in c.items() if k not in {"embedding", "_rowid"}},
             "rank": i, "score": -score if mode == "vector" else score}
            for i, (score, c) in enumerate(hits[:top_k], 1)]
