"""Analysis metric scaffolding — only evaluates fields with ground truth."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .models import Reference
from .structure_metrics import compute_structure_boundary_metrics


def _round4(value: float | None) -> float | None:
    return round(value, 4) if value is not None else None


@dataclass(frozen=True)
class AnalysisMetrics:
    key_correct: bool | None = None
    bpm_absolute_error: float | None = None
    meter_correct: bool | None = None
    # Primary section fields mirror MIREX/SongFormBench untrimmed hit rates.
    # Trimmed companions measure only interior structural boundaries.
    section_precision: float | None = None
    section_recall: float | None = None
    section_f1: float | None = None
    section_precision_3s: float | None = None
    section_recall_3s: float | None = None
    section_f1_3s: float | None = None
    section_precision_trimmed: float | None = None
    section_recall_trimmed: float | None = None
    section_f1_trimmed: float | None = None
    section_precision_trimmed_3s: float | None = None
    section_recall_trimmed_3s: float | None = None
    section_f1_trimmed_3s: float | None = None
    chord_precision: float | None = None
    chord_recall: float | None = None
    chord_f1: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "key_correct": self.key_correct,
            "bpm_absolute_error": (
                round(self.bpm_absolute_error, 3) if self.bpm_absolute_error is not None else None
            ),
            "meter_correct": self.meter_correct,
            "section_precision": _round4(self.section_precision),
            "section_recall": _round4(self.section_recall),
            "section_f1": _round4(self.section_f1),
            "section_precision_3s": _round4(self.section_precision_3s),
            "section_recall_3s": _round4(self.section_recall_3s),
            "section_f1_3s": _round4(self.section_f1_3s),
            "section_precision_trimmed": _round4(self.section_precision_trimmed),
            "section_recall_trimmed": _round4(self.section_recall_trimmed),
            "section_f1_trimmed": _round4(self.section_f1_trimmed),
            "section_precision_trimmed_3s": _round4(self.section_precision_trimmed_3s),
            "section_recall_trimmed_3s": _round4(self.section_recall_trimmed_3s),
            "section_f1_trimmed_3s": _round4(self.section_f1_trimmed_3s),
            "chord_precision": _round4(self.chord_precision),
            "chord_recall": _round4(self.chord_recall),
            "chord_f1": _round4(self.chord_f1),
        }


def compute_analysis_metrics(
    predicted_key: str | None,
    predicted_bpm: float | None,
    predicted_meter: str | None,
    predicted_sections: list[dict[str, Any]] | None,
    predicted_chords: list[dict[str, Any]] | None,
    reference: Reference,
) -> AnalysisMetrics:
    key_correct = None
    if reference.key is not None and predicted_key is not None:
        key_correct = predicted_key.strip().lower() == reference.key.strip().lower()

    bpm_abs = None
    if reference.bpm is not None and predicted_bpm is not None:
        bpm_abs = abs(predicted_bpm - reference.bpm)

    meter_correct = None
    if reference.meter is not None and predicted_meter is not None:
        meter_correct = predicted_meter.strip() == reference.meter.strip()

    section_p = section_r = section_f1 = None
    section_p3 = section_r3 = section_f13 = None
    section_tp = section_tr = section_tf1 = None
    section_tp3 = section_tr3 = section_tf13 = None
    if reference.sections:
        boundary_metrics = compute_structure_boundary_metrics(
            predicted_sections,
            reference.sections,
        )
        section_p = boundary_metrics.precision_05
        section_r = boundary_metrics.recall_05
        section_f1 = boundary_metrics.f1_05
        section_p3 = boundary_metrics.precision_3
        section_r3 = boundary_metrics.recall_3
        section_f13 = boundary_metrics.f1_3
        section_tp = boundary_metrics.precision_trimmed_05
        section_tr = boundary_metrics.recall_trimmed_05
        section_tf1 = boundary_metrics.f1_trimmed_05
        section_tp3 = boundary_metrics.precision_trimmed_3
        section_tr3 = boundary_metrics.recall_trimmed_3
        section_tf13 = boundary_metrics.f1_trimmed_3

    chord_p = chord_r = chord_f1 = None
    if reference.chords:
        # There is ground truth to score against. Zero predictions is a real
        # (worst-possible) baseline: recall and F1 are 0, not "not computable".
        ref_roots = [(c.get("root", ""), c.get("start", 0)) for c in reference.chords]
        pred_roots = [(c.get("root", ""), c.get("start", 0)) for c in (predicted_chords or [])]
        matched_c = sum(
            1 for r in ref_roots for p in pred_roots if r[0] == p[0] and abs(r[1] - p[1]) <= 0.5
        )
        chord_p = matched_c / len(pred_roots) if pred_roots else 0.0
        chord_r = matched_c / len(ref_roots) if ref_roots else 0.0
        chord_f1 = 2 * chord_p * chord_r / (chord_p + chord_r) if (chord_p + chord_r) > 0 else 0.0

    return AnalysisMetrics(
        key_correct=key_correct,
        bpm_absolute_error=bpm_abs,
        meter_correct=meter_correct,
        section_precision=section_p,
        section_recall=section_r,
        section_f1=section_f1,
        section_precision_3s=section_p3,
        section_recall_3s=section_r3,
        section_f1_3s=section_f13,
        section_precision_trimmed=section_tp,
        section_recall_trimmed=section_tr,
        section_f1_trimmed=section_tf1,
        section_precision_trimmed_3s=section_tp3,
        section_recall_trimmed_3s=section_tr3,
        section_f1_trimmed_3s=section_tf13,
        chord_precision=chord_p,
        chord_recall=chord_r,
        chord_f1=chord_f1,
    )
