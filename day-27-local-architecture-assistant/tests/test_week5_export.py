import importlib.util
import json
from pathlib import Path
import sqlite3

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "day-28-local-architecture-rag/prepare_week5.py"
spec = importlib.util.spec_from_file_location("prepare_week5", SCRIPT)
exporter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(exporter)


def fixture(tmp_path, monkeypatch):
    sources = [{"source": f"doc{i:02}." + ("md" if i < 9 else "kt"), "text": "snapshot " + str(i)} for i in range(22)]
    for s in sources: s["source_hash"] = exporter.digest(s["text"])
    corpus = exporter.digest(exporter.canonical([(s["source"], s["source_hash"]) for s in sources]))
    monkeypatch.setattr(exporter, "CORPUS", corpus)
    path = tmp_path / "old.sqlite3"
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE builds(run_id TEXT,data TEXT)")
        db.execute("CREATE TABLE sources(run_id TEXT,source TEXT,data TEXT)")
        # No chunks table: accidentally querying old vectors must fail.
        db.execute("INSERT INTO builds VALUES(?,?)", (exporter.RUN, json.dumps({"run_id": exporter.RUN, "corpus_hash": corpus})))
        db.executemany("INSERT INTO sources VALUES(?,?,?)", [(exporter.RUN, s["source"], json.dumps(s)) for s in sources])
    return path


def test_readonly_export_snapshots_only(tmp_path, monkeypatch):
    old = fixture(tmp_path, monkeypatch)
    before = old.read_bytes()
    dest = tmp_path / "K"
    assert exporter.export(old, dest) == 9
    assert len(list(dest.rglob("*.md"))) == 9
    assert not list(dest.rglob("*.kt")) and old.read_bytes() == before
    assert all(p.read_text().startswith("snapshot ") for p in dest.iterdir())
    with pytest.raises(ValueError): exporter.export(old, dest)
    with pytest.raises(ValueError): exporter.destination(exporter.REPO / ".local/day28")


@pytest.mark.parametrize("bad", ["hash", "missing", "run", "corpus", "text"])
def test_invalid_snapshot_no_partial_export(tmp_path, monkeypatch, bad):
    old = fixture(tmp_path, monkeypatch)
    with sqlite3.connect(old) as db:
        if bad == "missing": db.execute("DELETE FROM sources WHERE source='doc00.md'")
        elif bad == "run": db.execute("DELETE FROM builds")
        elif bad == "corpus": monkeypatch.setattr(exporter, "CORPUS", "bad")
        else:
            row = json.loads(db.execute("SELECT data FROM sources WHERE source='doc00.md'").fetchone()[0])
            row["source_hash" if bad == "hash" else "text"] = "tampered"
            db.execute("UPDATE sources SET data=? WHERE source='doc00.md'", (json.dumps(row),))
    dest = tmp_path / "K"
    with pytest.raises(ValueError): exporter.export(old, dest)
    assert not dest.exists()


def test_git_destination_refused(tmp_path):
    (tmp_path / ".git").mkdir()
    with pytest.raises(ValueError): exporter.destination(tmp_path / "K")
