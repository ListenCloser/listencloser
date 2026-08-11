"""Analysis metric scaffolding — only evaluates fields with ground truth."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .models import Reference


@dataclass(frozen=True)
class AnalysisMetrics:
    key_correct: bool | None = None
    bpm_absolute_error: float | None = None
    meter_correct: bool | None = None
    section_precision: float | None = None
    section_recall: float | None = None
    section_f1: float | None = None
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
            "section_precision": (
                round(self.section_precision, 4) if self.section_precision is not None else None
            ),
            "section_recall": (
                round(self.section_recall, 4) if self.section_recall is not None else None
            ),
            "section_f1": (round(self.section_f1, 4) if self.section_f1 is not None else None),
            "chord_precision": (
                round(self.chord_precision, 4) if self.chord_precision is not None else None
            ),
            "chord_recall": (
                round(self.chord_recall, 4) if self.chord_recall is not None else None
            ),
            "chord_f1": (round(self.chord_f1, 4) if self.chord_f1 is not None else None),
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
    if reference.sections and predicted_sections:
        ref_labels = [
            (s["start"], s["end"], s.get("label", ""))
            for s in reference.sections
            if "start" in s and "end" in s
        ]
        pred_labels = [(s["start"], s["end"], s.get("label", "")) for s in predicted_sections]
        matched = sum(
            1
            for r in ref_labels
            for p in pred_labels
            if abs(r[0] - p[0]) <= 1.0 and abs(r[1] - p[1]) <= 1.0
        )
        section_p = matched / len(pred_labels) if pred_labels else 0.0
        section_r = matched / len(ref_labels) if ref_labels else 0.0
        section_f1 = (
            2 * section_p * section_r / (section_p + section_r)
            if (section_p + section_r) > 0
            else 0.0
        )

    chord_p = chord_r = chord_f1 = None
    if reference.chords and predicted_chords:
        ref_roots = [(c.get("root", ""), c.get("start", 0)) for c in reference.chords]
        pred_roots = [(c.get("root", ""), c.get("start", 0)) for c in predicted_chords]
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
        chord_precision=chord_p,
        chord_recall=chord_r,
        chord_f1=chord_f1,
    )
