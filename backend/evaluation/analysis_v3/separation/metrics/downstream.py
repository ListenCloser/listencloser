"""Downstream MIR metrics for separated stems."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np


@dataclass(frozen=True)
class DownstreamMetrics:
    chord_accuracy: float | None = None
    beat_f1: float | None = None
    melody_accuracy: float | None = None
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "chord_accuracy": round(self.chord_accuracy, 4)
            if self.chord_accuracy is not None
            else None,
            "beat_f1": round(self.beat_f1, 4) if self.beat_f1 is not None else None,
            "melody_accuracy": round(self.melody_accuracy, 4)
            if self.melody_accuracy is not None
            else None,
            "notes": self.notes,
        }


def compute_chord_accuracy_on_stem(
    stem_audio: np.ndarray,
    sample_rate: int,
    reference_chords: list[dict[str, Any]] | None = None,
) -> float | None:
    """Compute chord accuracy on a separated stem.

    This is a placeholder for downstream evaluation.
    Actual implementation would use lv-chordia or similar.
    """
    return None


def compute_beat_f1_on_stem(
    stem_audio: np.ndarray,
    sample_rate: int,
    reference_beats: list[float] | None = None,
) -> float | None:
    """Compute beat F1 on a separated stem.

    This is a placeholder for downstream evaluation.
    Actual implementation would use mir_eval.beat.
    """
    return None


def compute_melody_accuracy_on_stem(
    stem_audio: np.ndarray,
    sample_rate: int,
    reference_melody: list[dict[str, Any]] | None = None,
) -> float | None:
    """Compute melody accuracy on a separated stem.

    This is a placeholder for downstream evaluation.
    Actual implementation would use transcription metrics.
    """
    return None
