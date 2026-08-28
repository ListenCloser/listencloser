"""Runtime and operational metrics for foundation model evaluation."""

from __future__ import annotations

import contextlib
import platform
import time
from dataclasses import dataclass, field
from typing import Any

import numpy as np


@dataclass
class RuntimeMetrics:
    latency_seconds: float | None = None
    latency_min: float | None = None
    latency_max: float | None = None
    latency_p95: float | None = None
    num_runs: int = 0
    peak_ram_mb: float | None = None
    peak_vram_mb: float | None = None
    audio_duration_seconds: float | None = None
    device: str = "cpu"
    python_version: str = ""
    platform: str = ""
    torch_version: str = ""
    error: str | None = None


@dataclass
class OperationalResult:
    candidate: str
    model_id: str
    install_success: bool = False
    install_error: str | None = None
    load_success: bool = False
    load_error: str | None = None
    load_time_seconds: float | None = None
    checkpoint_size_mb: float | None = None
    embedding_dim: int | None = None
    temporal: bool = False
    temporal_resolution: float | None = None
    cpu_latency_10s: RuntimeMetrics | None = None
    cpu_latency_30s: RuntimeMetrics | None = None
    cpu_latency_full: RuntimeMetrics | None = None
    determinism_stable: bool | None = None
    notes: str = ""
    extra: dict[str, Any] = field(default_factory=dict)


def measure_embedding_latency(
    adapter: Any,
    audio: np.ndarray,
    sample_rate: int,
    num_runs: int = 5,
    warmup_runs: int = 1,
) -> RuntimeMetrics:
    """Measure embedding latency with warm-up and multiple runs.

    Returns median latency. Also records min/max for spread analysis.
    """
    errors: list[str] = []

    for _ in range(warmup_runs):
        with contextlib.suppress(Exception):
            adapter.embed_audio(audio, sample_rate)

    latencies: list[float] = []
    for _ in range(num_runs):
        try:
            t0 = time.monotonic()
            result = adapter.embed_audio(audio, sample_rate)
            elapsed = time.monotonic() - t0
            if result.ok:
                latencies.append(elapsed)
            elif result.error:
                errors.append(result.error)
        except Exception as e:
            errors.append(str(e))

    return RuntimeMetrics(
        latency_seconds=float(np.median(latencies)) if latencies else None,
        latency_min=float(np.min(latencies)) if latencies else None,
        latency_max=float(np.max(latencies)) if latencies else None,
        latency_p95=float(np.percentile(latencies, 95)) if latencies else None,
        num_runs=len(latencies),
        audio_duration_seconds=len(audio) / sample_rate,
        device=adapter.device,
        python_version=platform.python_version(),
        platform=platform.platform(),
        torch_version=_get_torch_version(),
        error="; ".join(errors) if errors else None,
    )


def check_determinism(
    adapter: Any,
    audio: np.ndarray,
    sample_rate: int,
    num_runs: int = 3,
) -> bool:
    embeddings: list[np.ndarray] = []
    for _ in range(num_runs):
        result = adapter.embed_audio(audio, sample_rate)
        if result.ok and result.vector is not None:
            embeddings.append(result.vector)

    if len(embeddings) < 2:
        return False

    return all(
        np.allclose(embeddings[0], embeddings[i], atol=1e-6)
        for i in range(1, len(embeddings))
    )


def get_checkpoint_size(model_id: str) -> float | None:
    try:
        from huggingface_hub import model_info

        info = model_info(model_id)
        total_size = 0
        for sibling in info.siblings:
            if sibling.size is not None:
                total_size += sibling.size
        return total_size / (1024 * 1024) if total_size > 0 else None
    except Exception:
        return None


def _get_torch_version() -> str:
    try:
        import torch

        return torch.__version__
    except ImportError:
        return "not installed"


def generate_synthetic_audio(
    duration_seconds: float = 10.0,
    sample_rate: int = 24000,
    frequency: float = 440.0,
) -> np.ndarray:
    t = np.linspace(0, duration_seconds, int(sample_rate * duration_seconds), endpoint=False)
    audio = 0.5 * np.sin(2 * np.pi * frequency * t)
    audio += 0.3 * np.sin(2 * np.pi * (frequency * 2) * t)
    audio += 0.2 * np.sin(2 * np.pi * (frequency * 0.5) * t)
    return audio.astype(np.float32)
