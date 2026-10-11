"""Local owner configuration. Tokens are read from environment, never serialized."""
from dataclasses import dataclass, field
import json
import os
from pathlib import Path
import re
from urllib.parse import urlsplit

import knowledge as kn
from ollama_client import local_url
from workspace import read_source

MODEL = "qwen2.5-coder:7b-instruct-q4_K_M"
ID = re.compile(r"[a-z0-9_-]{1,64}\Z", re.ASCII)


@dataclass(frozen=True, repr=False)
class Config:
    workspace: Path
    knowledge: Path
    files: dict
    tokens: dict = field(repr=False)
    digest: str
    base_url: str = "http://127.0.0.1:11434"
    local_only_confirmed: bool = False

    def __post_init__(self):
        try:
            w, k = kn.local_root(self.workspace), kn.local_root(self.knowledge)
            kn.separate(k, w)
            if self.local_only_confirmed is not True:
                raise ValueError
            if not re.fullmatch(r"(?:sha256:)?[a-f0-9]{64}", self.digest):
                raise ValueError
            if urlsplit(self.base_url).hostname != "127.0.0.1":
                raise ValueError
            local_url(self.base_url)
            if not isinstance(self.files, dict) or not self.files or len(self.files) > 32:
                raise ValueError
            for key, filename in self.files.items():
                if not ID.fullmatch(key):
                    raise ValueError
                read_source(str(w), filename)
            if not isinstance(self.tokens, dict) or not 1 <= len(self.tokens) <= 16:
                raise ValueError
            for label, token in self.tokens.items():
                if not ID.fullmatch(label) or not re.fullmatch(r"[A-Za-z0-9_-]{43,128}", token):
                    raise ValueError
            if len(set(self.tokens.values())) != len(self.tokens):
                raise ValueError
            object.__setattr__(self, "workspace", w)
            object.__setattr__(self, "knowledge", k)
            object.__setattr__(self, "files", dict(self.files))
            object.__setattr__(self, "tokens", dict(self.tokens))
        except Exception:
            raise ValueError("Invalid local service configuration.") from None


def load_config(path):
    try:
        raw = Path(path).read_bytes()
        if len(raw) > 32 * 1024:
            raise ValueError
        value = json.loads(raw)
        if set(value) != {"workspace", "knowledge", "files", "token_env", "digest", "base_url", "local_only_confirmed"}:
            raise ValueError
        refs = value.pop("token_env")
        value["tokens"] = {label: os.environ[name] for label, name in refs.items()}
        return Config(**value)
    except Exception:
        raise ValueError("Invalid local service configuration.") from None
