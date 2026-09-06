"""Local dataset cache conventions for the evaluation corpus."""

from __future__ import annotations

import os
from pathlib import Path


def cache_dir() -> Path:
    """Return the dataset cache directory.

    Configurable via ``MUSIC_EVAL_CACHE_DIR``; defaults to
    ``backend/evaluation/.cache``.
    """
    env = os.environ.get("MUSIC_EVAL_CACHE_DIR")
    if env:
        return Path(env)
    return Path(__file__).resolve().parent.parent / ".cache"


def dataset_dir(name: str) -> Path:
    """Return the per-dataset cache directory (created lazily)."""
    return cache_dir() / name


def is_cached(path: Path) -> bool:
    return path.exists()
