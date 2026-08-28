"""Base adapter interface for foundation model evaluation."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

import numpy as np


@dataclass
class ModelMetadata:
    candidate: str
    model_id: str
    code_license: str | None = None
    weight_license: str | None = None
    training_data_notes: str | None = None
    embedding_dim: int | None = None
    temporal: bool = False
    temporal_resolution_seconds: float | None = None
    supports_audio: bool = True
    supports_text: bool = False
    supports_symbolic: bool = False
    checkpoint_size_mb: float | None = None
    upstream_repo: str | None = None
    upstream_commit: str | None = None
    notes: str = ""


@dataclass
class EmbeddingResult:
    vector: np.ndarray | None = None
    temporal_vectors: np.ndarray | None = None
    temporal_resolution_seconds: float | None = None
    dimensionality: int | None = None
    normalized: bool = False
    latency_seconds: float | None = None
    peak_ram_mb: float | None = None
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.error is None and self.vector is not None


class FoundationModelAdapter:
    name: str = "unknown"
    model_id: str = ""

    def __init__(self, device: str = "cpu"):
        self.device = device
        self._loaded = False

    def load(self) -> None:
        raise NotImplementedError

    def embed_audio(
        self,
        audio: np.ndarray,
        sample_rate: int,
    ) -> EmbeddingResult:
        raise NotImplementedError

    def embed_text(self, text: str) -> EmbeddingResult | None:
        return None

    def supports_text(self) -> bool:
        return False

    def supports_symbolic(self) -> bool:
        return False

    def embed_symbolic(self, midi_bytes: bytes) -> EmbeddingResult | None:
        return None

    def metadata(self) -> ModelMetadata:
        raise NotImplementedError

    def _timed_audio_embed(
        self,
        audio: np.ndarray,
        sample_rate: int,
    ) -> EmbeddingResult:
        t0 = time.monotonic()
        result = self.embed_audio(audio, sample_rate)
        result.latency_seconds = round(time.monotonic() - t0, 4)
        return result
