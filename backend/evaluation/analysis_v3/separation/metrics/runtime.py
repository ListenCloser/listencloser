"""Runtime and operational metrics for separation evaluation."""

from __future__ import annotations

import contextlib
import platform
import time
from dataclasses import dataclass
from typing import Any

import numpy as np


@dataclass
class RuntimeMetrics:
    latency_seconds: float | None = None
    latency_min: float | None = None
    latency_max: float | None = None
    latency_p95: float | None = None
    num_runs: int = 0
    audio_duration_seconds: float | None = None
    device: str = "cpu"
    python_version: str = ""
    platform: str = ""
    torch_version: str = ""
    error: str | None = None


def measure_latency(
    adapter: Any,
    audio: np.ndarray,
    sample_rate: int,
    num_runs: int = 3,
    warmup_runs: int = 1,
) -> RuntimeMetrics:
    """Measure latency with warm-up and multiple runs."""
    errors: list[str] = []

    for _ in range(warmup_runs):
        with contextlib.suppress(Exception):
            adapter.separate(audio, sample_rate)

    latencies: list[float] = []
    for _ in range(num_runs):
        try:
            t0 = time.monotonic()
            result = adapter.separate(audio, sample_rate)
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
    """Check if adapter produces deterministic results."""
    results: list[np.ndarray] = []
    for _ in range(num_runs):
        result = adapter.separate(audio, sample_rate)
        if result.ok and result.vocals is not None:
            results.append(result.vocals)

    if len(results) < 2:
        return False

    return all(np.allclose(results[0], results[i], atol=1e-06) for i in range(1, len(results)))


def generate_synthetic_audio(
    duration_seconds: float = 10.0,
    sample_rate: int = 44100,
    frequency: float = 440.0,
) -> np.ndarray:
    """Generate synthetic audio for testing."""
    t = np.linspace(0, duration_seconds, int(sample_rate * duration_seconds), endpoint=False)
    audio = 0.5 * np.sin(2 * np.pi * frequency * t)
    audio += 0.3 * np.sin(2 * np.pi * (frequency * 2) * t)
    audio += 0.2 * np.sin(2 * np.pi * (frequency * 0.5) * t)
    return audio.astype(np.float32)


def _get_torch_version() -> str:
    try:
        import torch

        return torch.__version__
    except ImportError:
        return "not installed"
