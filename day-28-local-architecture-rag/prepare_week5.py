"""Narrow pinned Day 21 Markdown exporter, outside the runtime assistant.

Never selects chunks/vectors, imports backend, or writes the historical database.
"""
import argparse
from contextlib import closing
import hashlib
import json
from pathlib import Path, PureWindowsPath
import sqlite3
import sys

sys.dont_write_bytecode = True
RUN = "3a3c3319-5516-4526-8e56-33ab1251da72"
CORPUS = "b1b9595ab50e225e077a2b78b48a90119519a1dc36141ef369a7bfb8b302c91d"
REPO = Path(__file__).resolve().parents[1]


def digest(text):
    return hashlib.sha256(text.encode("utf8")).hexdigest()


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def snapshots(database):
    try:
        with closing(sqlite3.connect(database.resolve(strict=True).as_uri() + "?mode=ro", uri=True)) as db:
            row = db.execute("SELECT data FROM builds WHERE run_id=?", (RUN,)).fetchone()
            if row is None:
                raise ValueError
            header = json.loads(row[0])
            if header["run_id"] != RUN or header["corpus_hash"] != CORPUS:
                raise ValueError
            sources = [json.loads(row[0]) for row in db.execute("SELECT data FROM sources WHERE run_id=? ORDER BY source", (RUN,))]
        if len(sources) != 22 or len({s["source"] for s in sources}) != 22:
            raise ValueError
        for source in sources:
            if digest(source["text"]) != source["source_hash"]:
                raise ValueError
        if digest(canonical([(s["source"], s["source_hash"]) for s in sources])) != CORPUS:
            raise ValueError
        chosen = {s["source"]: s["text"] for s in sources if s["source"].endswith(".md")}
        if len(chosen) != 9:
            raise ValueError
        for name in chosen:
            win = PureWindowsPath(name)
            if win.drive or win.root or "\\" in name or ":" in name or any(p in {"", ".", ".."} for p in name.split("/")):
                raise ValueError
        return chosen
    except (OSError, sqlite3.Error, TypeError, ValueError, KeyError, AttributeError):
        raise ValueError("Pinned Week 5 snapshot unavailable or invalid; export cancelled.") from None


def destination(path):
    path = Path(path).absolute()
    for part in (path, *path.parents):
        if part.is_symlink() or part.is_junction():
            raise ValueError("Destination links are forbidden.")
    resolved = path.resolve()
    if resolved.is_relative_to(REPO) or resolved == REPO or any((p / ".git").exists() for p in (resolved, *resolved.parents)):
        raise ValueError("Export destination must be outside Git checkouts.")
    if resolved.exists() and (not resolved.is_dir() or any(resolved.iterdir())):
        raise ValueError("Destination must be absent or empty; no overwrites.")
    return resolved


def export(database, target):
    target = destination(target)
    chosen = snapshots(database)  # Validate all snapshots before any write.
    target.mkdir(parents=True, exist_ok=True)
    for name, text in chosen.items():
        path = target / name
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("x", encoding="utf8", newline="\n") as stream:
            stream.write(text)
    return len(chosen)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--destination", required=True)
    args = parser.parse_args()
    try:
        count = export(REPO / "backend/.local/day21/index.sqlite3", args.destination)
        print(f"Exported {count} Markdown snapshots; no vectors copied.")
        return 0
    except (OSError, ValueError):
        print("Export failed: verify pinned source and empty local destination outside Git.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
