import sys
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import laa_service

import httpx
import pytest


@pytest.fixture(autouse=True)
def no_real_upstream(monkeypatch):
    """All tests inject MockTransport; accidentally accessing Ollama fails closed."""
    def fail(*args, **kwargs):
        raise AssertionError("Real httpx transport is prohibited in offline tests")
    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", fail)
