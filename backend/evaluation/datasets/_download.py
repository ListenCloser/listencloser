"""Shared download helper for dataset adapters.

Downloads are idempotent (skip cached files) and never write into the git repo.
"""

from __future__ import annotations

import os
from pathlib import Path
from urllib import request as urlrequest


def download(url: str, dest: Path) -> Path:
    """Download ``url`` to ``dest`` if not already present. Returns ``dest``."""
    if dest.exists() and dest.stat().st_size > 0:
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    try:
        with urlrequest.urlopen(url, timeout=60) as resp, open(tmp, "wb") as fh:
            while True:
                chunk = resp.read(1 << 16)
                if not chunk:
                    break
                fh.write(chunk)
        os.replace(tmp, dest)
    except Exception as exc:
        if tmp.exists():
            tmp.unlink(missing_ok=True)
        raise RuntimeError(f"Failed to download {url}: {exc}") from exc
    return dest
