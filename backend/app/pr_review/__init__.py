"""Day 32: bounded PR data analysis; never import or execute reviewed code."""
import os
import re
from pathlib import PurePosixPath

VERSION = 'day32-review-v1'
SIGNAL_PATH = '.github/workflows/day32-pr-signal.yml'
MAX_FILES, MAX_DIFF_BYTES, MAX_LINES = 10, 128 * 1024, 1000
MAX_SOURCE_BYTES, MAX_CORPUS_BYTES, MAX_SOURCES = 256 * 1024, 2 * 1024 * 1024, 25
MAX_CHUNKS, MAX_DIFF_TOKENS, MAX_INPUT_TOKENS = 160, 12000, 24000
TECHNICAL = {'configuration_error', 'github_error', 'incomplete_diff', 'provider_error',
             'validation_error', 'publication_error'}


class ReviewError(Exception):
    """Only fixed, content-free categories cross the CLI boundary."""
    def __init__(self, status, reason):
        self.status, self.reason = status, reason
        super().__init__(status + ': ' + reason)


def require(condition, status='github_error', reason='invalid_metadata'):
    if not condition:
        raise ReviewError(status, reason)


def positive(value):
    return type(value) is int and value > 0


def sha(value):
    require(isinstance(value, str) and re.fullmatch('[0-9a-f]{40}', value), reason='invalid_sha')
    return value


def repository(value):
    require(isinstance(value, str) and re.fullmatch(r'[A-Za-z0-9_-]+/[A-Za-z0-9_.-]+', value)
            and value.split('/')[-1] not in {'.', '..'}, 'configuration_error', 'invalid_repository')
    return value


def source_path(value):
    require(isinstance(value, str) and 0 < len(value) <= 512, 'unsupported_scope', 'invalid_path')
    p = PurePosixPath(value)
    blocked = {'.git', '.local', '.venv', 'venv', '__pycache__', 'build', 'evidence',
               '.gradle', '.idea', '.vscode', '.pytest_cache', '.mypy_cache', '.ruff_cache',
               '.cache', '.kotlin', 'node_modules', 'dist', 'local.properties'}
    require(not p.is_absolute() and str(p) == value and '\\' not in value and ':' not in value
            and all(x not in {'', '.', '..'} and x.lower() not in blocked
                    and not x.lower().startswith('.env') for x in value.split('/'))
            and not any(ord(c) < 32 or ord(c) == 127 for c in value)
            and p.suffix.lower() not in {'.key', '.pem', '.p12', '.pfx', '.jks', '.keystore'},
            'unsupported_scope', 'forbidden_path')
    return value


def reject_secrets(text):
    known = [os.getenv(k, '') for k in ('OPENAI_API_KEY', 'GITHUB_TOKEN', 'GH_TOKEN')]
    require(not any(len(v) >= 8 and v in text for v in known)
            and not re.search(r'(?:sk-[A-Za-z0-9_-]{20,}|gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})', text),
            'unsupported_scope', 'possible_secret')
