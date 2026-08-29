"""Measure HTDemucs CPU operational cost without making quality claims.

This runner uses deterministic synthetic audio so the measurement isolates model
runtime and memory from dataset I/O. It is evaluation-only and does not represent
Oracle production topology unless executed there.
"""

from __future__ import annotations

import argparse
import gc
import hashlib
import json
import os
import platform
import resource
import time
from importlib.metadata import version
from pathlib import Path
from typing import Any

import numpy as np

MODEL_NAME = "htdemucs"
MODEL_SIGNATURE = "955717e8"
CHECKPOINT_FILENAME = "955717e8-8726e21a.th"
DURATIONS_SECONDS = (10.0, 30.0, 180.0)
SAMPLE_RATE = 44100


def _max_rss_mb() -> float:
    value = float(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    if platform.system() == "Darwin":
        return value / (1024.0 * 1024.0)
    return value / 1024.0


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _synthetic_audio(duration_seconds: float, sample_rate: int = SAMPLE_RATE) -> np.ndarray:
    if duration_seconds <= 0:
        raise ValueError("duration_seconds must be positive")
    samples = int(round(duration_seconds * sample_rate))
    t = np.arange(samples, dtype=np.float64) / sample_rate
    audio = (
        0.45 * np.sin(2.0 * np.pi * 110.0 * t)
        + 0.30 * np.sin(2.0 * np.pi * 220.0 * t)
        + 0.20 * np.sin(2.0 * np.pi * 440.0 * t)
        + 0.05 * np.sin(2.0 * np.pi * 1760.0 * t)
    )
    return audio.astype(np.float32)


def _checkpoint_path() -> Path:
    return Path.home() / ".cache" / "torch" / "hub" / "checkpoints" / CHECKPOINT_FILENAME


def _run_once(model: Any, audio: np.ndarray, *, device: str) -> tuple[dict[str, Any], str]:
    import torch
    from demucs.apply import apply_model

    stereo = np.stack([audio, audio], axis=0)
    waveform = torch.from_numpy(stereo).float().unsqueeze(0).to(device)
    started = time.monotonic()
    with torch.no_grad():
        sources = apply_model(model, waveform, device=device, shifts=0)
    latency = time.monotonic() - started

    if sources.dim() == 4:
        sources = sources.squeeze(0)
    source_names = list(
        model.sources if hasattr(model, "sources") else ["drums", "bass", "other", "vocals"]
    )
    first_stem = sources[0].detach().cpu().numpy()
    first_stem_digest = hashlib.sha256(first_stem.tobytes()).hexdigest()
    shape = list(sources.shape)
    del first_stem, sources, waveform, stereo
    gc.collect()

    duration_seconds = len(audio) / SAMPLE_RATE
    return (
        {
            "audio_duration_seconds": duration_seconds,
            "latency_seconds": round(latency, 3),
            "real_time_factor": round(latency / duration_seconds, 4),
            "process_max_rss_mb": round(_max_rss_mb(), 2),
            "output_shape": shape,
            "source_names": source_names,
        },
        first_stem_digest,
    )


def run_operational_probe(*, device: str = "cpu") -> dict[str, Any]:
    if device != "cpu":
        raise ValueError("This operational gate is intentionally CPU-only")

    import torch
    from demucs.pretrained import get_model

    checkpoint = _checkpoint_path()
    checkpoint_present_before_load = checkpoint.is_file()
    started = time.monotonic()
    model = get_model(MODEL_NAME)
    model.eval()
    model.to(device)
    model_prepare_seconds = time.monotonic() - started

    checkpoint_metadata: dict[str, Any] = {
        "filename": CHECKPOINT_FILENAME,
        "present_before_load": checkpoint_present_before_load,
        "present_after_load": checkpoint.is_file(),
    }
    if checkpoint.is_file():
        checkpoint_metadata.update(
            {
                "size_mb": round(checkpoint.stat().st_size / (1024.0 * 1024.0), 2),
                "sha256": _sha256(checkpoint),
            }
        )

    measurements: list[dict[str, Any]] = []
    digests: dict[float, str] = {}
    failures: list[str] = []
    for duration in DURATIONS_SECONDS:
        audio = _synthetic_audio(duration)
        try:
            measurement, digest = _run_once(model, audio, device=device)
            measurements.append(measurement)
            digests[duration] = digest
        except Exception as exc:  # pragma: no cover - only real inference can exercise this
            failures.append(f"{duration:g}s: {type(exc).__name__}: {exc}")
        finally:
            del audio
            gc.collect()

    determinism: dict[str, Any]
    try:
        audio = _synthetic_audio(10.0)
        repeat, repeat_digest = _run_once(model, audio, device=device)
        determinism = {
            "duration_seconds": 10.0,
            "shifts": 0,
            "first_stem_sha256_equal": digests.get(10.0) == repeat_digest,
            "repeat_latency_seconds": repeat["latency_seconds"],
        }
    except Exception as exc:  # pragma: no cover - only real inference can exercise this
        determinism = {"error": f"{type(exc).__name__}: {exc}"}
        failures.append(f"determinism: {type(exc).__name__}: {exc}")

    payload = {
        "experiment": "separation_operational_cpu_v2",
        "evidence_scope": (
            "synthetic operational timing/memory only; not separation quality or downstream value"
        ),
        "topology": {
            "platform": platform.platform(),
            "machine": platform.machine(),
            "processor": platform.processor(),
            "cpu_count": os.cpu_count(),
            "device": device,
            "python_version": platform.python_version(),
            "torch_version": torch.__version__,
            "torch_num_threads": torch.get_num_threads(),
        },
        "separator": {
            "candidate": "HTDemucs",
            "demucs_package_version": version("demucs"),
            "model": MODEL_NAME,
            "model_signature": MODEL_SIGNATURE,
            "inference_shifts": 0,
            "model_prepare_seconds": round(model_prepare_seconds, 3),
            "checkpoint": checkpoint_metadata,
        },
        "sample_rate": SAMPLE_RATE,
        "measurements": measurements,
        "determinism": determinism,
        "success": not failures and len(measurements) == len(DURATIONS_SECONDS),
        "failures": failures,
    }
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Run HTDemucs CPU operational gate")
    parser.add_argument("--device", choices=["cpu"], default="cpu")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    payload = run_operational_probe(device=args.device)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2) + "\n")
    print(json.dumps(payload, indent=2))
    if not payload["success"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
