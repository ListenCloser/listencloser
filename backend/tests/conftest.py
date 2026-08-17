import os
import tempfile

os.environ.setdefault("ADAPTER_ROOT", tempfile.mkdtemp(prefix="adapter_root_"))

import pytest
from fastapi.testclient import TestClient

from auth_utils import limiter
from main import app

# Ask fixtures are defined in tests/fixtures/ask.py; re-export them so pytest
# discovers them without polluting the module namespace above.
from tests.fixtures.ask import (  # noqa: E402
    make_context,
    make_insight,
    no_selection_context,
    selection_context,
    selection_notation_context,
    whole_work_context,
)

__all__ = [
    "make_context",
    "make_insight",
    "selection_context",
    "whole_work_context",
    "no_selection_context",
    "selection_notation_context",
]


@pytest.fixture(autouse=True)
def disable_rate_limiter():
    """Disable slowapi rate limiter for unit tests to avoid cross-test pollution."""
    original = limiter.enabled
    limiter.enabled = False
    yield
    limiter.enabled = original


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c
