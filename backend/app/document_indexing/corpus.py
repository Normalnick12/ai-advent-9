import hashlib
import json
from dataclasses import dataclass
from pathlib import Path, PurePosixPath


ROOT = Path(__file__).resolve().parents[3]
MANIFEST = ROOT / "day-21-document-indexing/corpus.json"
SOURCE_TYPES = {"documentation", "spec", "backend", "android"}
BLOCKED = {".local", ".git", ".venv", "venv", "build", "__pycache__", "evidence", "archive"}


def digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def canonical(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


@dataclass(frozen=True)
class Source:
    source: str
    source_type: str
    text: str

    @property
    def source_hash(self):
        return digest(self.text)

    @property
    def title(self):
        return PurePosixPath(self.source).name


@dataclass(frozen=True)
class Snapshot:
    sources: tuple[Source, ...]
    manifest: dict

    @property
    def corpus_hash(self):
        return digest(canonical([(s.source, s.source_hash) for s in self.sources]))


def load_corpus(root: Path = ROOT, manifest_path: Path = MANIFEST) -> Snapshot:
    root = root.resolve()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    entries = manifest.get("sources", [])
    if not entries:
        raise ValueError("Manifest has no sources")
    seen, sources = set(), []
    for entry in entries:
        name, kind = entry["source"], entry["source_type"]
        path = PurePosixPath(name)
        if (name in seen or kind not in SOURCE_TYPES or path.is_absolute()
                or str(path) != name or "\\" in name or ":" in name
                or any(p in BLOCKED or p.startswith(".") or p == ".." for p in path.parts)
                or path.suffix not in {".md", ".py", ".kt"}):
            raise ValueError(f"Invalid corpus entry: {name}")
        resolved = (root / name).resolve()
        if not resolved.is_relative_to(root) or not resolved.is_file():
            raise ValueError(f"Source missing or outside repository: {name}")
        expected = {"backend": ".py", "android": ".kt", "spec": ".md", "documentation": ".md"}[kind]
        if path.suffix != expected:
            raise ValueError(f"Source type/extension mismatch: {name}")
        text = resolved.read_text(encoding="utf-8-sig")
        sources.append(Source(name, kind, text))
        seen.add(name)
    return Snapshot(tuple(sorted(sources, key=lambda s: s.source)), manifest)


def inventory(snapshot: Snapshot) -> str:
    lines = [f"Corpus: {snapshot.corpus_hash}"]
    for source in snapshot.sources:
        lines.append(f"{source.source_type:13} {len(source.text):7} chars {len(source.text.splitlines()):5} lines  {source.source}")
    lines.append(f"Total: {len(snapshot.sources)} files, {sum(len(s.text) for s in snapshot.sources)} characters, "
                 f"{sum(len(s.text.splitlines()) for s in snapshot.sources)} lines (normalized LF)")
    return "\n".join(lines)
