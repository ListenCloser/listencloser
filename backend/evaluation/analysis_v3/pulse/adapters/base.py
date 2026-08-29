"""Base adapter interface for pulse/beat evaluation."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

import numpy as np


@dataclass
class PulseMetadata:
    candidate: str
    engine: str
    code_license: str | None = None
    checkpoint_license: str | None = None
    upstream_repo: str | None = None
    upstream_version: str | None = None
    checkpoint_name: str | None = None
    checkpoint_size_mb: float | None = None
    training_datasets: tuple[str, ...] = ()
    held_out_datasets: tuple[str, ...] = ()
    supports_beats: bool = True
    supports_downbeats: bool = False
    supports_tempo: bool = True
    supports_meter: bool = False
    supports_local_tempo: bool = False
    notes: str = ""


@dataclass
class PulseResult:
    beats: list[float] = field(default_factory=list)
    downbeats: list[float] = field(default_factory=list)
    beat_positions: list[int] = field(default_factory=list)
    tempo_bpm: float | None = None
    meter_numerator: int | None = None
    meter_denominator: int | None = None
    confidence: list[float] = field(default_factory=list)
    latency_seconds: float | None = None
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.error is None and len(self.beats) > 0


class PulseAdapter:
    name: str = "unknown"
    engine: str = ""

    def __init__(self, device: str = "cpu"):
        self.device = device
        self._loaded = False

    def load(self) -> None:
        raise NotImplementedError

    def analyze(
        self,
        audio: np.ndarray,
        sample_rate: int,
    ) -> PulseResult:
        raise NotImplementedError

    def metadata(self) -> PulseMetadata:
        raise NotImplementedError

    def _timed_analyze(
        self,
        audio: np.ndarray,
        sample_rate: int,
    ) -> PulseResult:
        t0 = time.monotonic()
        result = self.analyze(audio, sample_rate)
        result.latency_seconds = round(time.monotonic() - t0, 4)
        return result
