"""Dataset adapters: resolve and cache pinned real-world clips.

Each adapter knows how to locate/download a single pinned clip and returns the
local paths to its audio + references. Adapters do NOT bundle audio in the repo;
they download to the cache (see ``cache.py``) or fail with a clear message when
manual acquisition is required.

Licensing: audio is never committed to the repo. Every manifest clip records its
own ``license`` field so redistribution constraints stay explicit.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass
class ResolvedClip:
    audio_path: str
    reference_midi_path: str | None = None
    reference_musicxml_path: str | None = None
    beats_path: str | None = None
    downbeats_path: str | None = None
    annotations_path: str | None = None


class DatasetAdapter(Protocol):
    name: str
    license: str

    def resolve(self, clip: dict[str, Any]) -> ResolvedClip:
        """Resolve (download/cache) a single clip and return local paths."""
        ...


class ManualAcquisitionError(RuntimeError):
    """Raised when a dataset requires manual download steps we cannot automate."""


class UnsupportedDatasetError(RuntimeError):
    """Raised when a dataset name has no registered adapter."""


_ADAPTERS: dict[str, DatasetAdapter] = {}


def register(adapter: DatasetAdapter) -> None:
    _ADAPTERS[adapter.name] = adapter


def get_adapter(name: str) -> DatasetAdapter:
    if name not in _ADAPTERS:
        raise UnsupportedDatasetError(
            f"No adapter registered for dataset '{name}'. Registered: {sorted(_ADAPTERS)}"
        )
    return _ADAPTERS[name]


def resolve_clip(clip: dict[str, Any]) -> ResolvedClip:
    adapter = get_adapter(clip["dataset"])
    return adapter.resolve(clip)


def available_datasets() -> list[str]:
    return sorted(_ADAPTERS)
