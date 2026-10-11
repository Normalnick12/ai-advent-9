"""Bounded access to a caller-owned, non-adversarial local checkout."""
from dataclasses import dataclass
import os
from pathlib import Path, PureWindowsPath
import stat

MAX_FILE_BYTES = 16 * 1024
RESERVED = {"CON", "PRN", "AUX", "NUL", "CONIN$", "CONOUT$"} | {
    f"{prefix}{n}" for prefix in ("COM", "LPT") for n in "123456789¹²³"
}


@dataclass(frozen=True)
class Source:
    name: str
    text: str

    @property
    def lines(self):
        # Kotlin line numbers follow LF, not Unicode splitlines separators.
        return self.text.removesuffix("\n").split("\n")


def read_source(workspace: str, filename: str) -> Source:
    windows = PureWindowsPath(filename)
    parts = filename.replace("\\", "/").split("/")
    if (not filename or windows.drive or windows.root or Path(filename).is_absolute()
            or ":" in filename or "\x00" in filename
            or any(p in {"", ".", ".."} or p.endswith((".", " ")) for p in parts)
            or any(p.split(".")[0].upper() in RESERVED for p in parts)
            or any(c in filename for c in '<>"|?*')
            or any(ord(c) < 32 for c in filename) or Path(parts[-1]).suffix != ".kt"):
        raise ValueError("Недопустимый относительный путь .kt-файла.")
    try:
        root = Path(workspace).resolve(strict=True)
        if not root.is_dir() or str(root).startswith(("\\\\", "//")):
            raise ValueError("Workspace должен быть локальным каталогом.")
        if os.name == "nt":
            import ctypes
            if ctypes.windll.kernel32.GetDriveTypeW(str(root.anchor)) == 4:
                raise ValueError("Сетевой Workspace не поддерживается.")
        selected = root
        for part in parts:
            selected /= part
            info = selected.lstat()
            if (stat.S_ISLNK(info.st_mode) or selected.is_junction()
                    or getattr(info, "st_file_attributes", 0) & 0x400):
                raise ValueError("Ссылки и reparse points внутри Workspace запрещены.")
        if not stat.S_ISREG(info.st_mode) or not selected.resolve(strict=True).is_relative_to(root):
            raise ValueError("Нужен обычный файл внутри Workspace.")
        with selected.open("rb") as stream:
            raw = stream.read(MAX_FILE_BYTES + 1)
    except (OSError, RuntimeError):
        raise OSError("Не удалось безопасно прочитать файл Workspace.") from None
    if len(raw) > MAX_FILE_BYTES:
        raise ValueError("Файл превышает 16 KiB; обрезка не выполняется.")
    try:
        text = raw.decode("utf-8-sig").replace("\r\n", "\n").replace("\r", "\n")
    except UnicodeError:
        raise ValueError("Файл должен иметь кодировку UTF-8.") from None
    if not text.strip():
        raise ValueError("Kotlin-файл пуст.")
    return Source("/".join(parts), text)
