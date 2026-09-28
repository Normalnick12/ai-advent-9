import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest

from app.document_indexing.chunking import STRATEGIES, chunk_source, token_count
from app.document_indexing.corpus import MANIFEST, ROOT, Source, load_corpus
from app.document_indexing.report import examples, prepare
from app.document_indexing.embedding import DIMENSION, Embeddings, OpenAIEmbedder
from app.document_indexing.pipeline import build
from app.document_indexing.storage import load, save


def assert_chunks(source, strategy):
    chunks = chunk_source(source, strategy)
    assert chunks == chunk_source(source, strategy)
    covered = set()
    for i, c in enumerate(chunks):
        a, b = c["start_char"], c["end_char"]
        assert c["text"] == source.text[a:b] and c["text"].strip()
        assert c["token_count"] == token_count(c["text"]) <= 500
        assert c["ordinal"] == i
        assert c["start_line"] == source.text.count("\n", 0, a) + 1
        assert c["end_line"] == source.text.count("\n", 0, b - 1) + 1
        if i:
            prev = chunks[i - 1]
            assert a > prev["start_char"]
            assert token_count(source.text[a:min(b, prev["end_char"])]) <= 50
        covered.update(range(a, b))
    assert all(i in covered for i, char in enumerate(source.text) if not char.isspace())
    assert len({c["chunk_id"] for c in chunks}) == len(chunks)
    return chunks


def test_token_windows_unicode_and_identity():
    text = ("Кириллица 🙂 日本語 <|endoftext|> function(x) { return x; }\n" * 120) + "конец"
    source = Source("fixture.kt", "android", text)
    chunks = assert_chunks(source, "fixed-size")
    assert len(chunks) > 2 and chunks[-1]["end_char"] == len(text)
    assert chunk_source(Source("empty.kt", "android", "\n  \t"), "fixed-size") == []


@pytest.mark.parametrize("suffix,kind,text", [
    ("md", "spec", "# Doc\nintro\n## Requirement\ntext\n```python\n# not a heading\n```\n### Scenario\n" + "наблюдение 🙂 " * 700),
    ("py", "backend", "# preamble\nimport os\n\nclass Store:\n    field = 1\n    @staticmethod\n    def save():\n        def inner():\n            return 1\n        return inner()\n\n    def big(self):\n" + "        value = 'данные 🙂'\n" * 600),
    ("kt", "android", "package lab\n\nclass Store {\n    fun save() = 1\n}\n\n" + "val value = \"данные 🙂\"; " * 600),
], ids=["markdown", "python", "kotlin"])
def test_structure_preserves_text(suffix, kind, text):
    chunks = assert_chunks(Source("fixture." + suffix, kind, text), "structure-aware")
    assert any(c["split_reason"] == "oversized_fallback" for c in chunks)
    if suffix == "md":
        assert not any("not a heading" in c["section"] for c in chunks)
        assert any("Scenario" in c["section"] for c in chunks)
    if suffix == "py":
        save = next(c for c in chunks if c["section"] == "Store.save")
        assert "@staticmethod" in save["text"] and "def inner" in save["text"]
    if suffix == "kt":
        assert all("formatting" in c["section"] for c in chunks)


def test_manifest_validation_and_snapshot(tmp_path):
    source = tmp_path / "sample.md"
    source.write_bytes(b"\xef\xbb\xbf# Title\r\ncontent\r\n")
    manifest = tmp_path / "corpus.json"
    entry = {"source": "sample.md", "source_type": "documentation"}
    manifest.write_text(json.dumps({"sources": [entry], "locations": []}))
    snapshot = load_corpus(tmp_path, manifest)
    source.write_text("edited")
    assert snapshot.sources[0].text == "# Title\ncontent\n"
    for name in ("../sample.md", ".env", ".local/sample.md", "missing.md"):
        manifest.write_text(json.dumps({"sources": [{**entry, "source": name}]}))
        with pytest.raises(ValueError):
            load_corpus(tmp_path, manifest)
    manifest.write_text(json.dumps({"sources": [entry, entry]}))
    with pytest.raises(ValueError):
        load_corpus(tmp_path, manifest)


def test_real_corpus_preview():
    snapshot = load_corpus(ROOT, MANIFEST)
    assert len(snapshot.sources) == 22
    data = prepare(snapshot)
    assert len(data["locations"]) == 4
    for strategy in STRATEGIES:
        for source in snapshot.sources:
            assert_chunks(source, strategy)
    for location in data["locations"]:
        output = examples(data, location["id"])
        assert "SOURCE LOCATION:" in output and "fixed-size:" in output
        assert "structure-aware deterministic chunking:" in output and "token_count" in output


@pytest.mark.parametrize("failure", [None, "count", "dimension"])
def test_embedding_adapter(failure):
    submitted = []

    def create(**kwargs):
        submitted.append(kwargs)
        items = [SimpleNamespace(index=i, embedding=[float(i)] * DIMENSION) for i in range(2)]
        if failure == "count":
            items.pop()
        if failure == "dimension":
            items[0].embedding.pop()
        return SimpleNamespace(data=items[::-1], usage=SimpleNamespace(total_tokens=7))

    adapter = OpenAIEmbedder(SimpleNamespace(embeddings=SimpleNamespace(create=create)))
    texts = ["first exact text", "second exact text"]
    if failure:
        with pytest.raises(ValueError):
            adapter.embed(texts)
    else:
        result = adapter.embed(texts)
        assert result.vectors[0] == [0.0] * DIMENSION
        assert result.vectors[1] == [1.0] * DIMENSION
        assert result.usage == 7
    assert submitted[0]["input"] is texts
    assert submitted[0]["model"] == "text-embedding-3-small"


class FakeEmbedder:
    def __init__(self, fail_call=None):
        self.calls = 0
        self.fail_call = fail_call

    def embed(self, texts):
        self.calls += 1
        if self.calls == self.fail_call:
            raise ValueError("fixture provider failure")
        return Embeddings([[float(token_count(text))] + [0.0] * (DIMENSION - 1) for text in texts],
                          sum(token_count(t) for t in texts))


def test_pipeline_roundtrip_failure_and_keyless_cli(tmp_path):
    source = tmp_path / "sample.md"
    source.write_text("# Example\n\n" + "Содержимое 🙂 indexing. " * 300, encoding="utf-8")
    manifest = tmp_path / "corpus.json"
    manifest.write_text(json.dumps({"sources": [{"source": "sample.md", "source_type": "documentation"}],
                                   "locations": [{"id": "example", "source": "sample.md", "kind": "heading", "anchor": "# Example"}]}))
    snapshot = load_corpus(tmp_path, manifest)
    preview = prepare(snapshot)
    assert "SOURCE LOCATION:" in examples(preview)
    database = tmp_path / "index.sqlite3"
    fake = FakeEmbedder()
    data = build(snapshot, fake, database)
    assert fake.calls == 2
    restored = load(data["run_id"], database)
    assert restored["sources"] == data["sources"]
    assert restored["chunks"] == data["chunks"]
    assert restored["config"] == data["config"]
    for chunks in restored["chunks"].values():
        assert all(c["embedding"][0] == token_count(c["text"]) for c in chunks)
    with pytest.raises(ValueError, match="provider failure"):
        build(snapshot, FakeEmbedder(fail_call=2), database)
    assert load(data["run_id"], database)["chunks"] == data["chunks"]
    # Failure after the build header was inserted rolls back the whole run.
    data["run_id"] = "failed-write"
    data["chunks"]["structure-aware"][0]["embedding"][0] = float("nan")
    with pytest.raises(ValueError):
        save(data, database)
    with pytest.raises(ValueError, match="Run not found"):
        load("failed-write", database)
    source.unlink()
    env = {k: v for k, v in os.environ.items() if k != "OPENAI_API_KEY"}
    for command in ("compare", "inspect"):
        result = subprocess.run([sys.executable, str(ROOT / "backend/scripts/day21_index.py"), command,
                                 "--db", str(database), "--run", restored["run_id"]],
                                capture_output=True, encoding="utf-8", env=env, check=True)
        assert "SOURCE LOCATION:" in result.stdout and "dimension=1536" in result.stdout
        assert "retrieval quality NOT TESTED" in result.stdout
