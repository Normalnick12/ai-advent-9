from contextlib import closing
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess

import pytest

import knowledge as kn
import knowledge_index as ix
from local_embeddings import RECIPE
import markdown_chunks as md

PROFILE = {**RECIPE, "model": "embed", "digest": "a" * 64, "dimension": 2}


def build(root, selection=None):
    snapshot = kn.scan(root, selection or kn.policy())
    chunks = md.chunk_snapshot(snapshot)
    ix.write(root, snapshot, PROFILE, chunks, [[1., 0.]] * len(chunks))
    return ix.read(root)


@pytest.mark.parametrize("name", ["../a.md", "a/../b.md", "C:a.md", "/a.md", "a.md:secret", "CON.md", "x./a.md", "a//b.md", "a\x00.md", "a?.md"])
def test_bad_relative(name):
    with pytest.raises(ValueError):
        kn.relative_name(name)


def test_discovery_policy_and_normalization(tmp_path):
    (tmp_path / "Правила.MD").write_bytes(b"\xef\xbb\xbf# Rules\r\nline\rnext")
    for folder in (".hidden", "build", "node_modules", ".laa", "venv"):
        (tmp_path / folder).mkdir()
        (tmp_path / folder / "bad.md").write_text("ignored")
    (tmp_path / "private.kt").write_text("SENTINEL")
    snapshot = kn.scan(tmp_path, kn.policy())
    assert snapshot.sources == {"Правила.MD": "# Rules\nline\nnext"}
    assert len(snapshot.excluded) == 5
    assert not kn.scan(tmp_path, kn.policy(excludes=["Правила.MD"])).sources
    assert kn.policy(kn.policy(includes=["Правила.MD"]), all_markdown=True)["includes"] is None
    with pytest.raises(ValueError):
        kn.policy(includes=["private.kt"])
    with pytest.raises(ValueError):
        kn.scan(tmp_path, kn.policy(includes=[".hidden/bad.md"]), explicit_includes=True)


@pytest.mark.parametrize("limit,value", [("MAX_DOC", 3), ("MAX_TOTAL", 5), ("MAX_DOCS", 1), ("MAX_ENTRIES", 1)])
def test_scan_limits(tmp_path, monkeypatch, limit, value):
    (tmp_path / "a.md").write_text("1234")
    (tmp_path / "b.md").write_text("1234")
    monkeypatch.setattr(kn, limit, value)
    with pytest.raises(ValueError):
        kn.scan(tmp_path, kn.policy())
    assert not (tmp_path / ".laa").exists()


def test_invalid_utf8_and_empty(tmp_path):
    with pytest.raises(ValueError):
        md.chunk_snapshot(kn.scan(tmp_path, kn.policy()))
    (tmp_path / "bad.md").write_bytes(b"\xff")
    with pytest.raises(ValueError):
        kn.scan(tmp_path, kn.policy())


def test_unreadable_source_is_not_deletion(tmp_path, monkeypatch):
    (tmp_path / "a.md").write_text("rule")
    old = build(tmp_path)
    original = Path.open
    def denied(path, *args, **kw):
        if path.name == "a.md":
            raise PermissionError
        return original(path, *args, **kw)
    monkeypatch.setattr(Path, "open", denied)
    with pytest.raises(PermissionError):
        ix.fresh(tmp_path, old)


@pytest.mark.parametrize("place", ["doc", "state", "index", "journal", "parent"])
def test_links_never_followed(tmp_path, place):
    root, outside = tmp_path / "K", tmp_path / "outside"
    root.mkdir(); outside.mkdir()
    (outside / "rule.md").write_text("private")
    try:
        if place == "doc":
            (root / "rule.md").symlink_to(outside / "rule.md")
            assert not kn.scan(root, kn.policy()).sources
            with pytest.raises(ValueError):
                kn.scan(root, kn.policy(includes=["rule.md"]), explicit_includes=True)
        elif place == "parent":
            (root / "sub").symlink_to(outside, target_is_directory=True)
            with pytest.raises(ValueError):
                kn.scan(root, kn.policy(includes=["sub/rule.md"]), explicit_includes=True)
        else:
            if place == "state":
                (root / ".laa").symlink_to(outside, target_is_directory=True)
            else:
                (root / ".laa").mkdir()
                name = "index.sqlite3" + ("-journal" if place == "journal" else "")
                (root / ".laa" / name).symlink_to(outside / "rule.md")
            with pytest.raises(ValueError):
                kn.index_path(root)
    except OSError as e:
        if getattr(e, "winerror", None) == 1314:
            pytest.skip("Symlink privilege unavailable")
        raise


def test_atx_fences_repeated_short_and_slices():
    text = "preamble\n# Team\nrule\n## Same\nfirst\n```kt\n# fake\n```\n## Same\nsecond\n"
    chunks = md.chunks_for("a.md", text)
    assert [c["section"] for c in chunks] == ["a.md", "Team", "Team / Same", "Team / Same"]
    assert len({c["chunk_id"] for c in chunks}) == 4
    for c in chunks:
        assert c["text"] == text[c["start_char"]:c["end_char"]]
        assert c["text_hash"] == kn.digest(c["text"])
        assert text.splitlines()[c["start_line"] - 1] in c["text"]
    assert len(md.chunks_for("a.md", "Header\n======\ntext")) == 1


def test_oversized_overlap_and_chunk_cap(monkeypatch):
    text = "x" * 4000
    chunks = md.chunks_for("a.md", text)
    assert [len(c["text"]) for c in chunks] == [1800, 1800, 760]
    assert chunks[1]["start_char"] == 1620
    monkeypatch.setattr(md, "MAX_CHUNKS", 1)
    with pytest.raises(ValueError):
        md.chunk_snapshot(kn.Snapshot(kn.policy(), {"a.md": text}, []))


def test_reopen_float32_relocation_readonly(tmp_path):
    root = tmp_path / "K"; root.mkdir()
    (root / "a.md").write_text("# Rule\nbody", encoding="utf8")
    index = build(root)
    assert index.chunks[0]["embedding"] == [1., 0.]
    before = kn.index_path(root).read_bytes()
    ix.fresh(root, index)
    assert kn.index_path(root).read_bytes() == before
    target = tmp_path / "moved"
    shutil.copytree(root, target)
    assert ix.fresh(target, ix.read(target)).hashes == index.hashes
    with closing(ix.connect(kn.index_path(target))) as db:
        with pytest.raises(sqlite3.OperationalError):
            db.execute("DELETE FROM chunks")


@pytest.mark.parametrize("change", ["edit", "new", "delete", "chunker", "corrupt", "fts", "foreign"])
def test_stale_or_corrupt(tmp_path, change):
    path = tmp_path / "a.md"; path.write_text("rule")
    index = build(tmp_path)
    if change == "edit":
        stamp = path.stat(); path.write_text("RULE"); os.utime(path, ns=(stamp.st_atime_ns, stamp.st_mtime_ns))
    elif change == "new":
        (tmp_path / "new.md").write_text("new")
    elif change == "delete":
        path.unlink()
    else:
        with closing(ix.connect(kn.index_path(tmp_path), readonly=False)) as db:
            if change == "chunker":
                meta = index.metadata; meta["chunker"] = {}
                db.execute("UPDATE metadata SET data=?", (kn.canonical(meta),))
            elif change == "corrupt":
                db.execute("UPDATE chunks SET vector=?", (b"no",))
            elif change == "fts":
                db.execute("DELETE FROM chunks_fts")
            else:
                db.execute("UPDATE chunks SET source='missing'")
            db.commit()
    with pytest.raises(RuntimeError):
        ix.fresh(tmp_path, ix.read(tmp_path))


def test_excluded_changes_and_deleted_explicit_selection(tmp_path):
    (tmp_path / "a.md").write_text("a")
    (tmp_path / "b.md").write_text("b")
    index = build(tmp_path, kn.policy(includes=["a.md"]))
    (tmp_path / "b.md").write_text("new")
    ix.fresh(tmp_path, index)
    (tmp_path / "a.md").unlink()
    assert kn.changes(kn.scan(tmp_path, index.metadata["policy"]), index.hashes)["deleted"] == ["a.md"]


@pytest.mark.parametrize("failure", ["source", "disk", "busy", "vector"])
def test_atomic_failures_preserve_committed_index(tmp_path, failure):
    path = tmp_path / "a.md"; path.write_text("old")
    build(tmp_path)
    before = kn.index_path(tmp_path).read_bytes()
    path.write_text("new")
    snapshot = kn.scan(tmp_path, kn.policy()); chunks = md.chunk_snapshot(snapshot)
    vectors = [[1., 0.]] if failure != "vector" else [[float("nan"), 0.]]
    def fail():
        if failure == "source":
            path.write_text("concurrent")
        elif failure == "disk":
            raise sqlite3.OperationalError("disk full")
    with closing(ix.connect(kn.index_path(tmp_path), readonly=False)) as blocker:
        if failure == "busy":
            blocker.execute("BEGIN IMMEDIATE")
        with pytest.raises(RuntimeError):
            ix.write(tmp_path, snapshot, PROFILE, chunks, vectors, before_commit=fail)
        blocker.rollback()
    assert kn.index_path(tmp_path).read_bytes() == before
    assert ix.read(tmp_path).hashes == {"a.md": kn.digest("old")}


def test_missing_fts(monkeypatch):
    def fail(*args, **kwargs):
        raise sqlite3.OperationalError
    monkeypatch.setattr(ix.sqlite3, "connect", fail)
    with pytest.raises(RuntimeError, match="FTS5"):
        ix.fts_available()


def test_unknown_schema_and_invalid_provenance_before_write(tmp_path):
    (tmp_path / "a.md").write_text("rule")
    index = build(tmp_path)
    before = kn.index_path(tmp_path).read_bytes()
    snapshot = kn.scan(tmp_path, kn.policy())
    chunks = md.chunk_snapshot(snapshot); chunks[0]["start_line"] = 99
    with pytest.raises(RuntimeError):
        ix.write(tmp_path, snapshot, PROFILE, chunks, [[1., 0.]])
    assert kn.index_path(tmp_path).read_bytes() == before
    with closing(ix.connect(kn.index_path(tmp_path), readonly=False)) as db:
        index.metadata["schema"] = 999
        db.execute("UPDATE metadata SET data=?", (kn.canonical(index.metadata),)); db.commit()
    with pytest.raises(RuntimeError, match="версия"):
        ix.read(tmp_path)


@pytest.mark.parametrize("bad", ["missing", "shape", "traversal"])
def test_corrupt_policy_is_safe_error(tmp_path, bad):
    (tmp_path / "a.md").write_text("rule")
    index = build(tmp_path)
    if bad == "missing": del index.metadata["policy"]
    elif bad == "shape": index.metadata["policy"] = []
    else: index.metadata["policy"] = {"includes": ["../private.md"], "excludes": []}
    with closing(ix.connect(kn.index_path(tmp_path), readonly=False)) as db:
        db.execute("UPDATE metadata SET data=?", (kn.canonical(index.metadata),)); db.commit()
    with pytest.raises(RuntimeError): ix.read(tmp_path)


@pytest.mark.skipif(os.name != "nt", reason="Windows junction")
@pytest.mark.parametrize("name", ["linked", ".laa"])
def test_actual_knowledge_junction(tmp_path, monkeypatch, name):
    root, outside = tmp_path / "K", tmp_path / "outside"
    root.mkdir(); outside.mkdir()
    (outside / "secret.md").write_text("private")
    script = "New-Item -ItemType Junction -Path $env:DAY28_LINK -Target $env:DAY28_TARGET | Out-Null"
    env = dict(os.environ, DAY28_LINK=str(root / name), DAY28_TARGET=str(outside))
    subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script], env=env, check=True)
    monkeypatch.setattr(Path, "open", lambda *a, **kw: pytest.fail("Read through junction"))
    if name == ".laa":
        with pytest.raises(ValueError): kn.index_path(root)
    else:
        assert not kn.scan(root, kn.policy()).sources
        with pytest.raises(ValueError): kn.scan(root, kn.policy(includes=["linked/secret.md"]))
