"""Task-standard music-structure boundary metrics.

Boundary detection is evaluated separately from semantic section labels/grouping.
The primary scores mirror MIREX/SongFormBench hit-rate metrics; trimmed interior
scores are retained as a product-truthfulness diagnostic so trivial track start/end
agreement cannot hide poor structural localization.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import mir_eval.segment
import numpy as np


@dataclass(frozen=True)
class StructureBoundaryMetrics:
    """MIREX-style hit rates plus trimmed interior-boundary diagnostics."""

    precision_05: float | None = None
    recall_05: float | None = None
    f1_05: float | None = None
    precision_3: float | None = None
    recall_3: float | None = None
    f1_3: float | None = None
    precision_trimmed_05: float | None = None
    recall_trimmed_05: float | None = None
    f1_trimmed_05: float | None = None
    precision_trimmed_3: float | None = None
    recall_trimmed_3: float | None = None
    f1_trimmed_3: float | None = None
    reference_boundary_count: int = 0
    predicted_boundary_count: int = 0
    reference_interior_boundary_count: int = 0
    predicted_interior_boundary_count: int = 0

    def to_dict(self) -> dict[str, int | float | None]:
        return {
            "precision_05": _rounded(self.precision_05),
            "recall_05": _rounded(self.recall_05),
            "f1_05": _rounded(self.f1_05),
            "precision_3": _rounded(self.precision_3),
            "recall_3": _rounded(self.recall_3),
            "f1_3": _rounded(self.f1_3),
            "precision_trimmed_05": _rounded(self.precision_trimmed_05),
            "recall_trimmed_05": _rounded(self.recall_trimmed_05),
            "f1_trimmed_05": _rounded(self.f1_trimmed_05),
            "precision_trimmed_3": _rounded(self.precision_trimmed_3),
            "recall_trimmed_3": _rounded(self.recall_trimmed_3),
            "f1_trimmed_3": _rounded(self.f1_trimmed_3),
            "reference_boundary_count": self.reference_boundary_count,
            "predicted_boundary_count": self.predicted_boundary_count,
            "reference_interior_boundary_count": self.reference_interior_boundary_count,
            "predicted_interior_boundary_count": self.predicted_interior_boundary_count,
        }


def _rounded(value: float | None) -> float | None:
    return round(value, 4) if value is not None else None


def _intervals(sections: list[dict[str, Any]] | None) -> np.ndarray:
    """Normalize valid section spans to an n-by-2 interval array."""
    normalized: list[tuple[float, float]] = []
    for section in sections or []:
        if "start" not in section or "end" not in section:
            continue
        start = float(section["start"])
        end = float(section["end"])
        if not np.isfinite(start) or not np.isfinite(end) or start < 0 or end <= start:
            continue
        normalized.append((start, end))
    normalized.sort(key=lambda interval: (interval[0], interval[1]))
    if not normalized:
        return np.empty((0, 2), dtype=float)
    return np.asarray(normalized, dtype=float)


def _boundary_count(intervals: np.ndarray) -> int:
    if len(intervals) == 0:
        return 0
    return len(mir_eval.util.intervals_to_boundaries(intervals))


def _interior_boundary_count(intervals: np.ndarray) -> int:
    return max(0, _boundary_count(intervals) - 2)


def _detection(
    reference: np.ndarray,
    predicted: np.ndarray,
    *,
    window: float,
    trim: bool,
) -> tuple[float, float, float]:
    precision, recall, f1 = mir_eval.segment.detection(
        reference,
        predicted,
        window=window,
        trim=trim,
    )
    return float(precision), float(recall), float(f1)


def compute_structure_boundary_metrics(
    predicted_sections: list[dict[str, Any]] | None,
    reference_sections: list[dict[str, Any]] | None,
) -> StructureBoundaryMetrics:
    """Score boundaries at MIREX/SongFormBench 0.5 s and 3 s windows.

    Primary ``precision/recall/f1`` fields use ``trim=False`` to mirror MSAF's
    ``HitRate_0.5*`` / ``HitRate_3*`` values and SongFormBench's published
    HR.5F/HR3F protocol.  The ``*_trimmed_*`` companion fields use ``trim=True``
    and therefore measure only interior structural boundaries.

    ``mir_eval.segment.detection`` performs one-to-one maximum boundary matching.
    With reference intervals and zero predictions, the task-standard score is a
    real zero.  If a clip has no interior reference boundary, trimmed fields are
    ``None`` rather than rewarding start/end agreement as evidence of structure.
    """
    reference = _intervals(reference_sections)
    predicted = _intervals(predicted_sections)
    reference_count = _boundary_count(reference)
    predicted_count = _boundary_count(predicted)
    reference_interior_count = _interior_boundary_count(reference)
    predicted_interior_count = _interior_boundary_count(predicted)

    if reference_count == 0:
        return StructureBoundaryMetrics(
            predicted_boundary_count=predicted_count,
            predicted_interior_boundary_count=predicted_interior_count,
        )

    p05, r05, f05 = _detection(reference, predicted, window=0.5, trim=False)
    p3, r3, f3 = _detection(reference, predicted, window=3.0, trim=False)

    trimmed: dict[str, float | None] = {
        "precision_trimmed_05": None,
        "recall_trimmed_05": None,
        "f1_trimmed_05": None,
        "precision_trimmed_3": None,
        "recall_trimmed_3": None,
        "f1_trimmed_3": None,
    }
    if reference_interior_count > 0:
        tp05, tr05, tf05 = _detection(reference, predicted, window=0.5, trim=True)
        tp3, tr3, tf3 = _detection(reference, predicted, window=3.0, trim=True)
        trimmed = {
            "precision_trimmed_05": tp05,
            "recall_trimmed_05": tr05,
            "f1_trimmed_05": tf05,
            "precision_trimmed_3": tp3,
            "recall_trimmed_3": tr3,
            "f1_trimmed_3": tf3,
        }

    return StructureBoundaryMetrics(
        precision_05=p05,
        recall_05=r05,
        f1_05=f05,
        precision_3=p3,
        recall_3=r3,
        f1_3=f3,
        **trimmed,
        reference_boundary_count=reference_count,
        predicted_boundary_count=predicted_count,
        reference_interior_boundary_count=reference_interior_count,
        predicted_interior_boundary_count=predicted_interior_count,
    )
