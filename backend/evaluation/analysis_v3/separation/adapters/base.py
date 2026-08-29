"""Base adapter interface for source separation evaluation."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

import numpy as np


@dataclass
class SeparationMetadata:
    candidate: str
    model_id: str
    code_license: str | None = None
    code_license_source: str | None = None
    weight_license: str | None = None
    weight_license_source: str | None = None
    upstream_repo: str | None = None
    upstream_version: str | None = None
    checkpoint_id: str | None = None
    checkpoint_file: str | None = None
    checkpoint_sha256: str | None = None
    checkpoint_sha256_prefix: str | None = None
    checkpoint_size_mb: float | None = None
    supports_vocals: bool = True
    supports_drums: bool = True
    supports_bass: bool = True
    supports_other: bool = True
    supports_piano: bool = False
    supports_guitar: bool = False
    num_stems: int = 4
    sample_rate: int = 44100
    notes: str = ""


@dataclass
class SeparationResult:
    vocals: np.ndarray | None = None
    drums: np.ndarray | None = None
    bass: np.ndarray | None = None
    other: np.ndarray | None = None
    piano: np.ndarray | None = None
    guitar: np.ndarray | None = None
    latency_seconds: float | None = None
    peak_ram_mb: float | None = None
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.error is None and any(
            s is not None for s in [self.vocals, self.drums, self.bass, self.other]
        )

    def get_stem(self, name: str) -> np.ndarray | None:
        return getattr(self, name, None)


class SeparationAdapter:
    name: str = "unknown"
    model_id: str = ""

    def __init__(self, device: str = "cpu"):
        self.device = device
        self._loaded = False

    def load(self) -> None:
        raise NotImplementedError

    def separate(
        self,
        audio: np.ndarray,
        sample_rate: int,
    ) -> SeparationResult:
        raise NotImplementedError

    def metadata(self) -> SeparationMetadata:
        raise NotImplementedError

    def _timed_separate(
        self,
        audio: np.ndarray,
        sample_rate: int,
    ) -> SeparationResult:
        t0 = time.monotonic()
        result = self.separate(audio, sample_rate)
        result.latency_seconds = round(time.monotonic() - t0, 4)
        return result
