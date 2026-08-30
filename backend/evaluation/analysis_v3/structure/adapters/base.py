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
    supports_batch = False

    def __init__(self, device: str = "cpu") -> None:
        self.device = device
        self._loaded = False

    def load(self) -> None:
        raise NotImplementedError

    def analyze(self, audio_path: str) -> StructureResult:
        raise NotImplementedError

    def analyze_many(self, audio_paths: list[str]) -> list[StructureResult]:
        """Analyze a candidate-native batch.

        Candidates should opt in with ``supports_batch = True`` only when their
        upstream API can share meaningful setup/model work across tracks. The
        default runner path remains per-clip so existing adapters retain their
        latency semantics.
        """
        raise NotImplementedError

    def metadata(self) -> StructureMetadata:
        raise NotImplementedError

    def timed_analyze(self, audio_path: str) -> StructureResult:
        start = time.monotonic()
        result = self.analyze(audio_path)
        result.latency_seconds = round(time.monotonic() - start, 4)
        return result

    def timed_analyze_many(
        self, audio_paths: list[str]
    ) -> tuple[list[StructureResult], float]:
        """Run eligible tracks and return results plus total candidate wall time.

        For ordinary adapters, preserve the existing per-clip timing contract.
        Batch-capable adapters invoke their native batch API once; per-clip
        ``latency_seconds`` stays unset because dividing a shared batch wall time
        would fabricate individual latency measurements.
        """
        start = time.monotonic()
        if self.supports_batch:
            results = self.analyze_many(audio_paths)
        else:
            results = [self.timed_analyze(audio_path) for audio_path in audio_paths]
        return results, round(time.monotonic() - start, 4)
