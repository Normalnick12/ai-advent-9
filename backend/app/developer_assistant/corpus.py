"""Explicit bounded Markdown snapshot; never crawl links or directories."""
import json
import stat
from pathlib import Path, PurePosixPath, PureWindowsPath

from app.document_indexing.corpus import ROOT, Source, Snapshot

MANIFEST = ROOT / 'day-31-developer-assistant/corpus.json'
MAX_DOC = 256 * 1024
MAX_TOTAL = 2 * 1024 * 1024
READMES = {'README.md', 'backend/README.md', 'android-app/README.md', 'scripts/README.md'}


def confined(root, name):
    root = Path(root).resolve(strict=True)
    path = root
    for part in PurePosixPath(name).parts:
        path /= part
        info = path.lstat()
        if (stat.S_ISLNK(info.st_mode) or path.is_junction()
                or getattr(info, 'st_file_attributes', 0) & 0x400):
            raise ValueError('unsafe_source_path')
    if not path.resolve().is_relative_to(root) or not path.is_file():
        raise ValueError('source_not_regular_file')
    return path


def snapshot(root=ROOT, manifest=MANIFEST):
    root, manifest = Path(root).resolve(strict=True), Path(manifest)
    try:
        manifest_name = manifest.absolute().relative_to(root).as_posix()
        data = json.loads(confined(root, manifest_name).read_text(encoding='utf-8-sig'))
        if not isinstance(data, dict) or set(data) != {'sources'} or not data['sources']:
            raise ValueError('invalid_manifest')
        seen, sources, total = set(), [], 0
        for entry in data['sources']:
            if not isinstance(entry, dict) or set(entry) != {'source', 'source_type'}:
                raise ValueError('invalid_manifest_entry')
            name = entry['source']
            if not isinstance(name, str):
                raise ValueError('invalid_source_name')
            parts = name.split('/')
            if (name in seen or entry['source_type'] != 'documentation'
                    or str(PurePosixPath(name)) != name or PureWindowsPath(name).drive
                    or PurePosixPath(name).is_absolute() or '\\' in name or ':' in name
                    or any(p in {'', '.', '..'} or p.startswith('.') or p.endswith((' ', '.')) for p in parts)
                    or any(ord(c) < 32 for c in name)
                    or not (name in READMES or name.startswith('docs/') and name.endswith('.md'))):
                raise ValueError('invalid_source_name')
            with confined(root, name).open('rb') as stream:
                raw = stream.read(MAX_DOC + 1)
            total += len(raw)
            if len(raw) > MAX_DOC or total > MAX_TOTAL:
                raise ValueError('corpus_size_limit')
            text = raw.decode('utf-8-sig').replace('\r\n', '\n').replace('\r', '\n')
            sources.append(Source(name, 'documentation', text))
            seen.add(name)
        normalized = {'sources': sorted(data['sources'], key=lambda s: s['source'])}
        return Snapshot(tuple(sorted(sources, key=lambda s: s.source)), normalized)
    except (OSError, UnicodeError, KeyError, TypeError, json.JSONDecodeError):
        raise ValueError('corpus_unavailable_or_invalid') from None
