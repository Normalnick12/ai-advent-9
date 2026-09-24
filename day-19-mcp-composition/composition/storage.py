"""Confined, atomic, content-addressed report publication."""
import hashlib
import os
from pathlib import Path
import stat
import tempfile

from .contracts import DependencyReport, SaveReceipt
from .report import canonical


class StorageFailure(Exception):
    pass


def safe_root(path):
    root = Path(os.path.abspath(path))
    # Service-owned root/parents; reject links rather than accepting redirected roots.
    if any(p.is_symlink() for p in (root, *root.parents)):
        raise StorageFailure("storage_root_symlink")
    if not root.is_dir() or root.resolve() != root:
        raise StorageFailure("storage_root_unavailable")
    return root


def read_regular(path):
    if path.is_symlink():
        raise StorageFailure("storage_target_symlink")
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_BINARY", 0))
    with os.fdopen(fd, "rb") as file:
        if not stat.S_ISREG(os.fstat(file.fileno()).st_mode):
            raise StorageFailure("storage_target_not_regular")
        return file.read()


class ReportStore:
    def __init__(self, root):
        self.root = Path(root)

    def save(self, report: DependencyReport) -> SaveReceipt:
        data = canonical(report.model_dump())
        sha = hashlib.sha256(data).hexdigest()
        temp = None
        try:
            root = safe_root(self.root)
            target = root / (sha + ".json")
            if target.is_symlink():
                raise StorageFailure("storage_target_symlink")
            if not target.exists():
                fd, name = tempfile.mkstemp(prefix=".pending-", dir=root)
                temp = Path(name)
                with os.fdopen(fd, "wb") as file:
                    file.write(data)
                    file.flush()
                    os.fsync(file.fileno())
                # Atomic no-clobber publication on the same filesystem. Unlike replace,
                # an existing final name is never overwritten.
                try:
                    os.link(temp, target)
                except FileExistsError:
                    pass
            if read_regular(target) != data:
                raise StorageFailure("storage_content_mismatch")
            return SaveReceipt(status="saved", lookup_id=report.lookup_id,
                               file_id=sha, sha256=sha, bytes=len(data))
        except OSError as exc:
            raise StorageFailure("storage_io_error; publication_may_have_occurred") from exc
        finally:
            if temp is not None:
                temp.unlink(missing_ok=True)
