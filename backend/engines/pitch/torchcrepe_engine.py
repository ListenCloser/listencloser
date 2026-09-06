"""torchcrepe-backed experimental Pitch Contour interpretation."""

from __future__ import annotations

import hashlib
import importlib.metadata
import importlib.resources
import io
import math
from typing import Any

import numpy as np
import soundfile as sf

from engines.pitch.pyin import FMAX_HZ, FMIN_HZ, HOP_SECONDS, hz_to_midi_cents

_MODEL = "tiny"
_PERIODICITY_THRESHOLD = 0.21


def _asset_sha256() -> str | None:
    try:
        asset = importlib.resources.files("torchcrepe").joinpath("assets/tiny.pth")
        return hashlib.sha256(asset.read_bytes()).hexdigest()
    except (FileNotFoundError, ModuleNotFoundError, OSError):
        return None


def estimate_pitch_contour(wav_bytes: bytes) -> dict[str, Any]:
    """Estimate F0 with torchcrepe tiny + Viterbi decoding on CPU."""
    try:
        import torch
        import torchcrepe
    except ImportError as exc:
        raise RuntimeError(
            "torchcrepe is not installed. Install the backend worker dependency group."
        ) from exc

    audio, sample_rate = sf.read(io.BytesIO(wav_bytes), dtype="float32", always_2d=True)
    if audio.size == 0 or sample_rate <= 0:
        raise ValueError("decoded audio is empty or has an invalid sample rate")

    input_channels = int(audio.shape[1])
    mono = np.mean(audio, axis=1, dtype=np.float32)
    hop_length = max(1, int(round(sample_rate * HOP_SECONDS)))
    tensor = torch.from_numpy(mono).unsqueeze(0)

    pitch, periodicity = torchcrepe.predict(
        tensor,
        int(sample_rate),
        hop_length,
        FMIN_HZ,
        FMAX_HZ,
        _MODEL,
        return_periodicity=True,
        batch_size=1024,
        device="cpu",
        pad=True,
    )
    pitch_values = pitch.squeeze(0).detach().cpu().numpy()
    periodicity_values = periodicity.squeeze(0).detach().cpu().numpy()

    frames: list[dict[str, Any]] = []
    for index, (pitch_hz, score) in enumerate(zip(pitch_values, periodicity_values, strict=True)):
        hz = float(pitch_hz)
        periodicity_score = float(score)
        finite_pitch = math.isfinite(hz) and hz > 0
        voiced = (
            finite_pitch
            and math.isfinite(periodicity_score)
            and periodicity_score >= _PERIODICITY_THRESHOLD
        )
        frames.append(
            {
                "frame": index,
                "time_seconds": index * hop_length / sample_rate,
                "pitch_hz": hz if voiced else None,
                "pitch_cents": hz_to_midi_cents(hz) if voiced else None,
                "voiced": voiced,
                "voiced_probability": None,
                "method_score": periodicity_score if math.isfinite(periodicity_score) else None,
                "method_score_kind": "periodicity",
            }
        )

    return {
        "engine": {
            "name": "torchcrepe",
            "version": importlib.metadata.version("torchcrepe"),
            "method": "CREPE tiny + Viterbi",
            "model": "tiny.pth",
            "model_sha256": _asset_sha256(),
            "license": "MIT",
        },
        "preprocessing": {
            "input_channels": input_channels,
            "downmix": "mean" if input_channels > 1 else "already_mono",
            "sample_rate_hz": int(sample_rate),
            "hop_length_samples": hop_length,
            "hop_seconds": hop_length / sample_rate,
            "fmin_hz": FMIN_HZ,
            "fmax_hz": FMAX_HZ,
            "centered_frames": True,
            "pitch_cents_reference": "absolute MIDI cents; A4=440 Hz=6900 cents",
            "voicing_rule": (
                f"torchcrepe periodicity >= {_PERIODICITY_THRESHOLD}; method-specific threshold"
            ),
        },
        "frames": frames,
    }
