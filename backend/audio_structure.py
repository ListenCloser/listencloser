"""Audio-derived metrical and functional structure.

Compatibility alias for the canonical structure engine seam in
:mod:`engines.structure.allin1_engine`.  A song's beat grid and form belong to
the original recording and must retain seconds-based evidence so a person can
hear what each claim refers to.

The optional engine is All-In-One.  It is kept behind a small adapter because
its PyTorch/NATTEN runtime is significantly heavier than the core worker.  An
unavailable optional engine never turns a successful transcription into a
failed import.
"""

from __future__ import annotations

import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from engines.structure.allin1_engine import AllInOneEngine


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
    engine: str = "allin1"

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

    Delegate to the canonical engine adapter so there is exactly one allin1
    invocation and normalization path.  ``model`` is kept for API compatibility
    and selects a non-default model when provided.
    """
    engine = AllInOneEngine(model=model) if model else AllInOneEngine()
    result = engine.analyze(str(Path(path)))
    if result is None:
        return None
    return StructureResult(
        bpm=result.bpm,
        beats=result.beats,
        downbeats=result.downbeats or [],
        beat_positions=result.beat_positions,
        segments=[
            Segment(start=seg["start"], end=seg["end"], label=seg["label"])
            for seg in result.segments
        ],
        model=result.provenance.model or os.environ.get("ALLIN1_MODEL", "harmonix-all"),
        engine=result.provenance.engine,
    )


def result_dict(result: StructureResult) -> dict[str, Any]:
    """Useful for diagnostics/tests without exposing raw model activations."""
    return asdict(result)
