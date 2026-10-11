import os
from pathlib import Path
import subprocess

import pytest

from workspace import MAX_FILE_BYTES, read_source


def test_utf8_nested_file_and_line_numbers(tmp_path):
    folder = tmp_path / "Код с пробелами"
    folder.mkdir()
    (folder / "A.kt").write_bytes(b"\xef\xbb\xbfclass A\r\n\r\n// end\r\n")
    result = read_source(str(tmp_path), "Код с пробелами/A.kt")
    assert result.lines == ["class A", "", "// end"]
    assert result.name == "Код с пробелами/A.kt"


@pytest.mark.parametrize("name", ["../A.kt", "/A.kt", "C:A.kt", "C:/A.kt", "\\\\host\\A.kt",
    "\\\\?\\C:\\A.kt", "A.kt:secret", "x/../A.kt", "x./A.kt", "x /A.kt", "A.py", "NUL.kt", ""])
def test_unsafe_names_never_open(tmp_path, name, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Invalid path attempted content read")
    monkeypatch.setattr(Path, "open", forbidden)
    with pytest.raises(ValueError):
        read_source(str(tmp_path), name)


@pytest.mark.parametrize("raw", [b"", b" \n", b"\xff", b"x" * (MAX_FILE_BYTES + 1)])
def test_unusable_content(tmp_path, raw):
    (tmp_path / "A.kt").write_bytes(raw)
    with pytest.raises(ValueError):
        read_source(str(tmp_path), "A.kt")


def test_exact_limit_missing_and_directory(tmp_path):
    (tmp_path / "A.kt").write_bytes(b"x" * MAX_FILE_BYTES)
    assert len(read_source(str(tmp_path), "A.kt").text) == MAX_FILE_BYTES
    with pytest.raises(OSError):
        read_source(str(tmp_path), "missing.kt")
    (tmp_path / "directory.kt").mkdir()
    with pytest.raises(ValueError):
        read_source(str(tmp_path), "directory.kt")


@pytest.mark.parametrize("directory", [False, True])
def test_symlink_to_sibling_with_same_prefix(tmp_path, directory, monkeypatch):
    root = tmp_path / "workspace"
    outside = tmp_path / "workspace-other"
    root.mkdir()
    outside.mkdir()
    (outside / "A.kt").write_text("external", encoding="utf-8")
    link = root / ("linked" if directory else "A.kt")
    try:
        link.symlink_to(outside if directory else outside / "A.kt", target_is_directory=directory)
    except OSError:
        pytest.skip("OS does not permit symlink creation")
    monkeypatch.setattr(Path, "open", lambda *a, **k: pytest.fail("Read through symlink"))
    with pytest.raises(ValueError):
        read_source(str(root), "linked/A.kt" if directory else "A.kt")


@pytest.mark.skipif(os.name != "nt", reason="Windows junction")
def test_windows_junction(tmp_path, monkeypatch):
    root, outside = tmp_path / "workspace", tmp_path / "workspace-other"
    root.mkdir()
    outside.mkdir()
    (outside / "A.kt").write_text("external", encoding="utf-8")
    # Native PowerShell end-to-end, no shell-built deletion commands.
    script = "New-Item -ItemType Junction -Path $env:DAY27_LINK -Target $env:DAY27_TARGET | Out-Null"
    env = dict(os.environ, DAY27_LINK=str(root / "link"), DAY27_TARGET=str(outside))
    subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script], env=env, check=True)
    monkeypatch.setattr(Path, "open", lambda *a, **k: pytest.fail("Read through junction"))
    with pytest.raises(ValueError):
        read_source(str(root), "link/A.kt")


@pytest.mark.skipif(os.name == "nt", reason="POSIX FIFO")
def test_fifo_rejected_without_open(tmp_path):
    os.mkfifo(tmp_path / "pipe.kt")
    with pytest.raises(ValueError):
        read_source(str(tmp_path), "pipe.kt")
