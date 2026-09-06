"""Stable filesystem anchors for repository-level backend tests.

Tests that inspect cross-project configuration should name the repository resource
explicitly instead of hand-counting ``Path.parents`` from each test module. Keep
layout knowledge here so structural rewrites have one test-only seam to update.
"""

from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = BACKEND_ROOT.parent
WEB_ROOT = REPOSITORY_ROOT / "apps" / "web"


def repository_path(*parts: str) -> Path:
    """Return a path rooted at the repository checkout."""
    return REPOSITORY_ROOT.joinpath(*parts)
