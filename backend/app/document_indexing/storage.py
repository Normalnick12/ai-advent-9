import json
import sqlite3
from contextlib import closing
from pathlib import Path

from .chunking import STRATEGIES
from .corpus import ROOT, canonical

DATABASE = ROOT / "backend/.local/day21/index.sqlite3"


def save(data, path: Path = DATABASE):
    path.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(path)) as db, db:
        db.execute("CREATE TABLE IF NOT EXISTS builds (run_id TEXT PRIMARY KEY, data TEXT NOT NULL)")
        db.execute("CREATE TABLE IF NOT EXISTS sources (run_id TEXT, source TEXT, data TEXT NOT NULL, PRIMARY KEY(run_id, source))")
        db.execute("""CREATE TABLE IF NOT EXISTS chunks (
            run_id TEXT, strategy TEXT, source TEXT, ordinal INTEGER, chunk_id TEXT, data TEXT NOT NULL,
            PRIMARY KEY(run_id, chunk_id), UNIQUE(run_id, strategy, source, ordinal))""")
        header = {k: v for k, v in data.items() if k not in {"sources", "chunks"}}
        header["counts"] = {s: len(data["chunks"][s]) for s in STRATEGIES}
        db.execute("INSERT INTO builds VALUES (?, ?)", (data["run_id"], canonical(header)))
        db.executemany("INSERT INTO sources VALUES (?, ?, ?)",
                       [(data["run_id"], s["source"], canonical(s)) for s in data["sources"]])
        for strategy in STRATEGIES:
            db.executemany("INSERT INTO chunks VALUES (?, ?, ?, ?, ?, ?)",
                           [(data["run_id"], strategy, c["source"], c["ordinal"], c["chunk_id"], canonical(c))
                            for c in data["chunks"][strategy]])


def load(run_id: str, path: Path = DATABASE):
    with closing(sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)) as db:
        row = db.execute("SELECT data FROM builds WHERE run_id=?", (run_id,)).fetchone()
        if row is None:
            raise ValueError("Run not found")
        data = json.loads(row[0])
        data["sources"] = [json.loads(r[0]) for r in db.execute(
            "SELECT data FROM sources WHERE run_id=? ORDER BY source", (run_id,))]
        data["chunks"] = {}
        for strategy in STRATEGIES:
            data["chunks"][strategy] = [json.loads(r[0]) for r in db.execute(
                "SELECT data FROM chunks WHERE run_id=? AND strategy=? ORDER BY source, ordinal", (run_id, strategy))]
            if len(data["chunks"][strategy]) != data["counts"][strategy] or not data["chunks"][strategy]:
                raise ValueError("Incomplete strategy pair")
        data["observations"]["sqlite_bytes_at_read"] = path.stat().st_size
        return data
