"""Content-free error categories, still compatible with CLI RuntimeError."""


class RuntimeFailure(RuntimeError):
    def __init__(self, code, message, *, rejected=False):
        super().__init__(message)
        self.code = code
        self.rejected = rejected


class WorkspaceUnavailable(OSError):
    """Preserves CLI file-error semantics while allowing HTTP's safe 404."""
