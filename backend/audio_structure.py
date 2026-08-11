"""Audio-derived metrical and functional structure.

This is deliberately separate from :mod:`analyze`, which interprets the
transcribed MIDI.  A song's beat grid and form belong to the original recording
and must retain seconds-based evidence so a person can hear what each claim
refers to.

The optional engine is All-In-One.  It is kept behind a small adapter because
its PyTorch/NATTEN runtime is significantly heavier than the core worker.  An
unavailable optional engine never turns a successful transcription into a
failed import.
"""

from __future__ import annotations

import importlib
import logging
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger("audio_structure")


@dataclass(frozen=True)
class Segment:
    start: float
    end: float
    label: str


@dataclass(frozen=True)
class StructureResult:
    bpm: float
    beats: list[float]
    downbeats: list[float]
    beat_positions: list[int]
    segments: list[Segment]
    model: str
    engine: str = "all-in-one"

    def evidence(self) -> dict[str, Any]:
        """JSON-safe aggregate evidence for the summary claim."""
        return {
            "bpm": self.bpm,
            "beat_count": len(self.beats),
            "downbeat_count": len(self.downbeats),
            "segment_count": len(self.segments),
            "model": self.model,
            "engine": self.engine,
        }


def enabled() -> bool:
    """Whether this deployment opted into the optional structure engine."""
    return os.environ.get("ALLIN1_ENABLED", "false").lower() in {"1", "true", "yes"}


def analyze_file(path: str | Path, model: str | None = None) -> StructureResult | None:
    """Return All-In-One structure for a decoded WAV, or ``None`` when disabled.

    The import happens here rather than at module import time so the ordinary
    API process can start while the heavyweight worker image is being rolled
    out.  Callers persist results only after this returns a complete result.
    """
    if not enabled():
        return None

    try:
        allin1 = importlib.import_module("allin1")
    except ImportError as exc:
        logger.warning("allin1_not_installed", extra={"reason": str(exc)})
        return None

    selected_model = model or os.environ.get("ALLIN1_MODEL", "harmonix-all")
    device = os.environ.get("ALLIN1_DEVICE", "cpu")
    try:
        raw = allin1.analyze(str(path), model=selected_model, device=device)
    except Exception:
        logger.exception("allin1_analysis_failed", extra={"model": selected_model})
        return None

    # allin1 returns a dataclass today, but normalize by attribute instead of
    # coupling persistence to its internal result serialization.
    segments = [
        Segment(
            start=round(float(item.start), 3),
            end=round(float(item.end), 3),
            label=str(item.label).strip().lower() or "section",
        )
        for item in (getattr(raw, "segments", None) or [])
        if float(item.end) > float(item.start) >= 0
    ]
    beats = [round(float(value), 3) for value in (getattr(raw, "beats", None) or [])]
    downbeats = [round(float(value), 3) for value in (getattr(raw, "downbeats", None) or [])]
    positions = [int(value) for value in (getattr(raw, "beat_positions", None) or [])]
    bpm = round(float(getattr(raw, "bpm", 0.0) or 0.0), 2)
    if bpm <= 0 or not beats:
        logger.warning("allin1_incomplete_result", extra={"model": selected_model})
        return None
    return StructureResult(
        bpm=bpm,
        beats=beats,
        downbeats=downbeats,
        beat_positions=positions,
        segments=segments,
        model=selected_model,
    )


def result_dict(result: StructureResult) -> dict[str, Any]:
    """Useful for diagnostics/tests without exposing raw model activations."""
    return asdict(result)
