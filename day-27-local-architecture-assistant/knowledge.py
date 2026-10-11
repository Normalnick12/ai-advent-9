"""Bounded local Markdown selection. Paths/content never leave the machine."""
from dataclasses import dataclass
from pathlib import Path, PureWindowsPath
import hashlib
import json
import os
import stat

from workspace import RESERVED

MAX_DOC = 256 * 1024
MAX_TOTAL = 4 * 1024 * 1024
MAX_DOCS = 500
MAX_ENTRIES = 10000
BLOCKED = {"venv", "node_modules", "build", "__pycache__"}


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def relative_name(value):
    if not isinstance(value, str):
        raise ValueError("Недопустимый относительный путь.")
    parts = value.replace("\\", "/").split("/")
    win = PureWindowsPath(value)
    if (not value or win.drive or win.root or ":" in value
            or any(p in {"", ".", ".."} or p.endswith((".", " ")) for p in parts)
            or any(p.split(".")[0].upper() in RESERVED for p in parts)
            or any(c in value for c in '<>"|?*') or any(ord(c) < 32 for c in value)):
        raise ValueError("Недопустимый относительный путь.")
    return "/".join(parts)


def local_root(value):
    if not value:
        raise ValueError("Укажите --knowledge или LAA_KNOWLEDGE.")
    p = Path(value).resolve(strict=True)
    if not p.is_dir() or str(p).startswith(("\\\\", "//")):
        raise ValueError("Нужен локальный каталог.")
    if os.name == "nt":
        import ctypes
        if ctypes.windll.kernel32.GetDriveTypeW(str(p.anchor)) == 4:
            raise ValueError("Сетевые каталоги не поддерживаются.")
    return p


def linked(path, info=None):
    info = info or path.lstat()
    return bool(stat.S_ISLNK(info.st_mode) or path.is_junction()
                or getattr(info, "st_file_attributes", 0) & 0x400)


def confined(root, name, *, missing=False):
    path = root
    for part in relative_name(name).split("/"):
        path /= part
        try:
            info = path.lstat()
        except FileNotFoundError:
            if missing:
                continue
            raise
        if linked(path, info):
            raise ValueError("Ссылки/reparse points запрещены.")
    if not path.resolve(strict=False).is_relative_to(root):
        raise ValueError("Путь выходит за разрешённый каталог.")
    return path


def index_path(root):
    p = confined(root, ".laa/index.sqlite3", missing=True)
    # SQLite may open these sidecars itself.
    for suffix in ("-journal", "-wal", "-shm"):
        confined(root, ".laa/index.sqlite3" + suffix, missing=True)
    if p.exists() and not p.is_file():
        raise ValueError("Index должен быть обычным файлом.")
    return p


def separate(root, workspace):
    w = local_root(workspace)
    if root.is_relative_to(w) or w.is_relative_to(root):
        raise ValueError("Knowledge и Workspace должны быть раздельными каталогами.")


def policy(old=None, *, includes=None, excludes=None, all_markdown=False):
    result = dict(old or {"includes": None, "excludes": []})
    if all_markdown and includes is not None:
        raise ValueError("--all-markdown несовместим с --include.")
    if all_markdown:
        result = {"includes": None, "excludes": []}
    if includes is not None:
        result["includes"] = sorted(set(relative_name(n) for n in includes))
        if any(Path(n).suffix.lower() != ".md" for n in result["includes"]):
            raise ValueError("--include принимает только Markdown.")
    if excludes is not None:
        result["excludes"] = sorted(set(relative_name(n) for n in excludes))
    return result


@dataclass
class Snapshot:
    policy: dict
    sources: dict
    excluded: list

    @property
    def hashes(self):
        return {n: digest(t) for n, t in self.sources.items()}

    @property
    def corpus_hash(self):
        return digest(canonical(sorted(self.hashes.items())))


def scan(root, selection, *, explicit_includes=False):
    sources, excluded, seen = {}, [], set()
    total = entries = 0
    include = selection["includes"]

    def visit(folder):
        nonlocal total, entries
        with os.scandir(folder) as children:
            # Bound discovery before sorting; never follow excluded directories.
            names = []
            for entry in children:
                entries += 1
                if entries > MAX_ENTRIES:
                    raise ValueError("Превышен лимит directory entries.")
                names.append(entry.name)
        for name in sorted(names):
            p = folder / name
            rel = p.relative_to(root).as_posix()
            info = p.lstat()
            if linked(p, info):
                if include and rel in include:
                    raise ValueError("Выбранный документ является ссылкой.")
                excluded.append((rel, "link"))
                continue
            blocked = name.startswith(".") or name in BLOCKED
            omitted = any(rel == e or rel.startswith(e + "/") for e in selection["excludes"])
            if blocked or omitted:
                excluded.append((rel, "excluded"))
                continue
            if stat.S_ISDIR(info.st_mode):
                if include is None or any(n.startswith(rel + "/") for n in include):
                    visit(p)
                continue
            if p.suffix.lower() != ".md" or (include is not None and rel not in include):
                continue
            relative_name(rel)
            if not stat.S_ISREG(info.st_mode):
                raise ValueError("Документ должен быть обычным файлом.")
            seen.add(rel)
            with p.open("rb") as stream:
                raw = stream.read(MAX_DOC + 1)
            total += len(raw)
            if len(raw) > MAX_DOC or total > MAX_TOTAL or len(sources) >= MAX_DOCS:
                raise ValueError("Превышен лимит документов Knowledge.")
            try:
                text = raw.decode("utf-8-sig").replace("\r\n", "\n").replace("\r", "\n")
            except UnicodeError:
                raise ValueError("Markdown должен быть UTF-8.") from None
            sources[rel] = text

    # Validate explicit/stored paths independently of the directory walker.
    for name in include or []:
        if any(part.startswith(".") or part in BLOCKED for part in name.split("/")):
            raise ValueError("Служебный путь нельзя включить.")
        p = confined(root, name, missing=not explicit_includes)
        if explicit_includes and not p.is_file():
            raise ValueError("Выбранный Markdown отсутствует.")
    visit(root)
    return Snapshot(selection, sources, excluded)


def changes(snapshot, old_hashes):
    now = snapshot.hashes
    return {
        "added": sorted(now.keys() - old_hashes.keys()),
        "deleted": sorted(old_hashes.keys() - now.keys()),
        "changed": sorted(n for n in now.keys() & old_hashes.keys() if now[n] != old_hashes[n]),
        "unchanged": sorted(n for n in now.keys() & old_hashes.keys() if now[n] == old_hashes[n]),
    }
