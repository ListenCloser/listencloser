"""PESTO-backed experimental Pitch Contour interpretation."""

from __future__ import annotations

import hashlib
import importlib.resources
import io
import math
from functools import lru_cache
from typing import Any

import numpy as np
import soundfile as sf

from engines.pitch.pyin import FMAX_HZ, FMIN_HZ, HOP_SECONDS, hz_to_midi_cents

_MODEL = "mir-1k_g7"
_VOICING_THRESHOLD = 0.5


def _asset_sha256() -> str | None:
    try:
        asset = importlib.resources.files("pesto").joinpath("weights/mir-1k_g7.ckpt")
        return hashlib.sha256(asset.read_bytes()).hexdigest()
    except (FileNotFoundError, ModuleNotFoundError, OSError):
        return None


@lru_cache(maxsize=8)
def _load_model(sample_rate: int):
    import pesto

    model = pesto.load_model(
        _MODEL,
        step_size=HOP_SECONDS * 1000,
        sampling_rate=sample_rate,
    ).to("cpu")
    model.reduction = "alwa"
    model.eval()
    return model


def estimate_pitch_contour(wav_bytes: bytes) -> dict[str, Any]:
    """Estimate F0 with PESTO mir-1k_g7 on CPU."""
    try:
        import pesto
        import torch
    except ImportError as exc:
        raise RuntimeError(
            "pesto-pitch is not installed. Install the backend worker dependency group."
        ) from exc

    audio, sample_rate = sf.read(io.BytesIO(wav_bytes), dtype="float32", always_2d=True)
    if audio.size == 0 or sample_rate <= 0:
        raise ValueError("decoded audio is empty or has an invalid sample rate")

    input_channels = int(audio.shape[1])
    mono = np.mean(audio, axis=1, dtype=np.float32)
    tensor = torch.from_numpy(mono)
    model = _load_model(int(sample_rate))

    with torch.inference_mode():
        pitch, confidence, _amplitude = model(
            tensor,
            sr=int(sample_rate),
            convert_to_freq=True,
            return_activations=False,
        )

    pitch_values = pitch.detach().cpu().numpy().reshape(-1)
    confidence_values = confidence.detach().cpu().numpy().reshape(-1)
    hop_seconds = float(model.hop_size) / 1000.0

    frames: list[dict[str, Any]] = []
    for index, (pitch_hz, score) in enumerate(
        zip(pitch_values, confidence_values, strict=True)
    ):
        hz = float(pitch_hz)
        confidence_score = float(score)
        finite_pitch = math.isfinite(hz) and FMIN_HZ <= hz <= FMAX_HZ
        voiced = (
            finite_pitch
            and math.isfinite(confidence_score)
            and confidence_score >= _VOICING_THRESHOLD
        )
        frames.append(
            {
                "frame": index,
                "time_seconds": index * hop_seconds,
                "pitch_hz": hz if voiced else None,
                "pitch_cents": hz_to_midi_cents(hz) if voiced else None,
                "voiced": voiced,
                "voiced_probability": None,
                "method_score": confidence_score if math.isfinite(confidence_score) else None,
                "method_score_kind": "voicing_confidence",
            }
        )

    return {
        "engine": {
            "name": "pesto",
            "version": pesto.__version__,
            "method": "PESTO ALWA",
            "model": _MODEL,
            "model_sha256": _asset_sha256(),
            "license": "LGPL-3.0",
        },
        "preprocessing": {
            "input_channels": input_channels,
            "downmix": "mean" if input_channels > 1 else "already_mono",
            "sample_rate_hz": int(sample_rate),
            "hop_length_samples": max(1, int(round(hop_seconds * sample_rate))),
            "hop_seconds": hop_seconds,
            "fmin_hz": FMIN_HZ,
            "fmax_hz": FMAX_HZ,
            "centered_frames": True,
            "pitch_cents_reference": "absolute MIDI cents; A4=440 Hz=6900 cents",
            "voicing_rule": (
                f"PESTO voicing confidence >= {_VOICING_THRESHOLD}; method-specific threshold"
            ),
        },
        "frames": frames,
    }
