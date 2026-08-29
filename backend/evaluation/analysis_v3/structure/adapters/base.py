"""Candidate-neutral adapter contract for music-structure evaluation."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class StructureMetadata:
    candidate: str
    engine: str
    code_license: str | None = None
    checkpoint_license: str | None = None
    upstream_repo: str | None = None
    upstream_version: str | None = None
    checkpoint_name: str | None = None
    training_datasets: tuple[str, ...] = ()
    held_out_datasets: tuple[str, ...] = ()
    training_partition: str | None = None
    held_out_partition: str | None = None
    split_source: str | None = None
    notes: str = ""


@dataclass
class StructureResult:
    segments: list[dict[str, Any]] = field(default_factory=list)
    latency_seconds: float | None = None
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.error is None and bool(self.segments)


class StructureAdapter:
    """Research adapter contract; candidate dependencies remain isolated."""

    name = "unknown"
    engine = ""

    def __init__(self, device: str = "cpu") -> None:
        self.device = device
        self._loaded = False

    def load(self) -> None:
        raise NotImplementedError

    def analyze(self, audio_path: str) -> StructureResult:
        raise NotImplementedError

    def metadata(self) -> StructureMetadata:
        raise NotImplementedError

    def timed_analyze(self, audio_path: str) -> StructureResult:
        start = time.monotonic()
        result = self.analyze(audio_path)
        result.latency_seconds = round(time.monotonic() - start, 4)
        return result
