"""Small pitch-local runtime selector for the Pitch Contour capability."""

from __future__ import annotations

from typing import Any


def estimate_pitch_contour(wav_bytes: bytes, name: str = "pyin") -> dict[str, Any]:
    """Run one explicitly selected F0 engine without fallback."""
    if name == "pyin":
        from engines.pitch.pyin import estimate_pitch_contour as estimate_pyin

        return estimate_pyin(wav_bytes)
    if name == "torchcrepe":
        from engines.pitch.torchcrepe_engine import estimate_pitch_contour as estimate_torchcrepe

        return estimate_torchcrepe(wav_bytes)
    if name == "pesto":
        from engines.pitch.pesto_engine import estimate_pitch_contour as estimate_pesto

        return estimate_pesto(wav_bytes)
    raise ValueError(f"Unknown pitch contour engine: {name}")
