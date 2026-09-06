"""Pinned ChordMini checkpoint acquisition.

The checkpoint is fetched only when the user explicitly selects ChordMini.
Every cached/downloaded artifact is verified against the immutable upstream Git
blob before inference, so a network/cache failure cannot silently change model
identity.
"""

from __future__ import annotations

import os
import tempfile
import urllib.request
from pathlib import Path

from engines.harmony._chordmini_runtime import (
    CHECKPOINT_NAME,
    UPSTREAM_COMMIT,
    validate_checkpoint,
)

_CHECKPOINT_URL = (
    "https://raw.githubusercontent.com/ptnghia-j/ChordMini/"
    f"{UPSTREAM_COMMIT}/checkpoints/{CHECKPOINT_NAME}"
)


def checkpoint_source_url() -> str:
    return _CHECKPOINT_URL


def resolve_checkpoint(configured_path: str | None = None) -> Path:
    """Return a verified pinned checkpoint, downloading it on first explicit use."""
    if configured_path:
        path = Path(configured_path).expanduser()
        validate_checkpoint(path)
        return path

    cache_root = Path(
        os.getenv(
            "CHORDMINI_CACHE_DIR",
            Path.home() / ".cache" / "listencloser" / "chordmini",
        )
    ).expanduser()
    cache_dir = cache_root / UPSTREAM_COMMIT
    checkpoint_path = cache_dir / CHECKPOINT_NAME

    if checkpoint_path.is_file():
        try:
            validate_checkpoint(checkpoint_path)
            return checkpoint_path
        except RuntimeError:
            checkpoint_path.unlink(missing_ok=True)

    cache_dir.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            dir=cache_dir,
            prefix=f".{CHECKPOINT_NAME}.",
            suffix=".download",
            delete=False,
        ) as handle:
            temporary_path = Path(handle.name)
            with urllib.request.urlopen(_CHECKPOINT_URL, timeout=120) as response:
                while chunk := response.read(1024 * 1024):
                    handle.write(chunk)
        validate_checkpoint(temporary_path)
        temporary_path.replace(checkpoint_path)
        return checkpoint_path
    except Exception as exc:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
        raise RuntimeError(
            "ChordMini checkpoint could not be acquired from its pinned upstream artifact. "
            "Set CHORDMINI_CHECKPOINT_PATH to a verified local copy if worker egress is disabled."
        ) from exc
