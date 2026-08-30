"""Temporary evaluation-run import shim for PR #596 only.

The dedicated result workflow invokes Python from the repository root while the
production/evaluation packages live under ``backend/``.  Extending this package
path lets the one-shot external corpus run import the exact repository modules
without copying their implementation.  This file is deleted after the
machine-readable result is committed; it is not intended to merge.
"""

from __future__ import annotations

import sys
from pathlib import Path

_BACKEND = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(_BACKEND))
__path__.append(str(_BACKEND / "evaluation"))
