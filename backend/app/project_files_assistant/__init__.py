"""Bounded project-file operations; no execution of inspected code."""
import hashlib
import json
import os
from pathlib import Path, PurePosixPath, PureWindowsPath
import re
import stat
import tempfile

ROOT = Path(__file__).resolve().parents[3]
DAY = "day-34-project-files-assistant"
SOURCES = ("backend/app/first_rag/core.py",
           "backend/app/developer_assistant/service.py",
           "backend/app/support_assistant/rag.py")
TARGET = "docs/search.md"
MAX_FILE, MAX_TOTAL, MAX_RESULT, MAX_DOC = 65536, 262144, 12288, 16384


class FileAgentError(ValueError):
    """Only fixed categories, never arbitrary file content or exception messages."""


def require(condition, code):
    if not condition:
        raise FileAgentError(code)


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False)


def digest(value):
    return hashlib.sha256(value if isinstance(value, bytes) else value.encode("utf-8")).hexdigest()


def name(value):
    require(isinstance(value, str) and 0 < len(value) <= 512, "invalid_path")
    p = PurePosixPath(value)
    require(str(p) == value and not p.is_absolute() and not PureWindowsPath(value).drive
            and "\\" not in value and ":" not in value, "invalid_path")
    for part in value.split("/"):
        require(part not in {"", ".", ".."} and not part.startswith(".")
                and not part.endswith((" ", "."))
                and not re.match(r"(?i)^(con|prn|aux|nul|com[0-9¹²³]|lpt[0-9¹²³])(?:\.|$)", part)
                and not any(ord(c) < 32 or ord(c) == 127 or c in '<>"|?*' for c in part),
                "invalid_path")
    return value


def guard(path, root=None):
    """Check lexical containment and every existing ancestor before resolving."""
    path = Path(path).absolute()
    if root is not None:
        root = Path(root).absolute()
        require(path.is_relative_to(root), "outside_root")
    for entry in reversed((path, *path.parents)):
        try:
            info = entry.lstat()
        except FileNotFoundError:
            continue
        require(not stat.S_ISLNK(info.st_mode)
                and not entry.is_junction()
                and not getattr(info, "st_file_attributes", 0) & 0x400, "unsafe_link")
        require(not stat.S_ISREG(info.st_mode) or info.st_nlink == 1, "unsafe_hardlink")
    if root is not None:
        require(path.resolve().is_relative_to(root.resolve()), "outside_root")
    return path


def bounded(path, limit=MAX_FILE):
    path = guard(path)
    require(path.is_file(), "not_regular_file")
    with path.open("rb") as stream:
        raw = stream.read(limit + 1)
    require(len(raw) <= limit, "file_size_limit")
    raw.decode("utf-8-sig")  # refuse binary/non-UTF-8
    return raw


def clean_text(text):
    require(isinstance(text, str), "invalid_text")
    secrets = [os.environ.get(key, "") for key in ("OPENAI_API_KEY", "GITHUB_TOKEN", "GH_TOKEN")]
    require(not any(len(s) >= 8 and s in text for s in secrets)
            and not re.search(r"(?:sk-[A-Za-z0-9_-]{20,}|gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})", text),
            "possible_secret")
    return text


def read_json(path):
    def unique(pairs):
        out = {}
        for key, value in pairs:
            require(key not in out, "duplicate_json_key")
            out[key] = value
        return out
    return json.loads(bounded(path, 4 * 1024 * 1024).decode("utf-8"),
                      object_pairs_hook=unique)


def write_json(path, value, *, exclusive=False):
    path = guard(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = (clean_text(canonical(value)) + "\n").encode("utf-8")
    if exclusive:
        with path.open("xb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        return
    fd, temp = tempfile.mkstemp(prefix="metadata-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        guard(path)
        os.replace(temp, path)
    finally:
        Path(temp).unlink(missing_ok=True)


def safe_terminal(text):
    return "".join(c if (ord(c) >= 32 and not 127 <= ord(c) <= 159) or c in "\n\t"
                   else f"\\u{ord(c):04x}" for c in str(text))
