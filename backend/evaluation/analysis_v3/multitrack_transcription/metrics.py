"""Task-standard metrics for Analysis V3 multi-instrument transcription evaluation."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import asdict, dataclass
from typing import Literal

import mir_eval
import numpy as np

ProgramMode = Literal["ignore", "family", "exact"]
DRUM_LABEL = 128


@dataclass(frozen=True)
class NoteEvent:
    pitch: int
    start: float
    end: float
    program: int = 0
    is_drum: bool = False


@dataclass(frozen=True)
class MatchMetrics:
    reference_notes: int
    predicted_notes: int
    matched_notes: int
    precision: float
    recall: float
    f1: float


def _label(note: NoteEvent, mode: ProgramMode) -> int | None:
    if mode == "ignore":
        return None
    if note.is_drum:
        return DRUM_LABEL
    if mode == "family":
        return note.program // 8
    return note.program


def _midi_to_hz(pitch: int) -> float:
    return 440.0 * (2.0 ** ((pitch - 69) / 12.0))


def _mir_eval_match_count(
    reference: list[NoteEvent],
    predicted: list[NoteEvent],
    *,
    onset_tolerance_s: float,
    require_offset: bool,
) -> int:
    if not reference or not predicted:
        return 0

    ref_intervals = np.asarray([[note.start, note.end] for note in reference], dtype=float)
    pred_intervals = np.asarray([[note.start, note.end] for note in predicted], dtype=float)
    ref_pitches = np.asarray([_midi_to_hz(note.pitch) for note in reference], dtype=float)
    pred_pitches = np.asarray([_midi_to_hz(note.pitch) for note in predicted], dtype=float)
    matching = mir_eval.transcription.match_notes(
        ref_intervals,
        ref_pitches,
        pred_intervals,
        pred_pitches,
        onset_tolerance=onset_tolerance_s,
        pitch_tolerance=50.0,
        offset_ratio=0.2 if require_offset else None,
        offset_min_tolerance=0.05,
        strict=False,
    )
    return len(matching)


def match_notes(
    reference: Iterable[NoteEvent],
    predicted: Iterable[NoteEvent],
    *,
    onset_tolerance_s: float = 0.05,
    require_offset: bool = False,
    program_mode: ProgramMode = "ignore",
) -> MatchMetrics:
    """Score AMT notes with mir_eval maximum bipartite matching.

    The flat view follows mir_eval/MIREX-style note tracking: +-50 ms onset,
    50-cent pitch tolerance, and optionally the larger of 20% reference-note
    duration or 50 ms for offsets. Program-aware views partition notes by GM
    family or exact MIDI program before applying the same task-standard matcher.
    """

    references = list(reference)
    predictions = list(predicted)
    if program_mode == "ignore":
        matched = _mir_eval_match_count(
            references,
            predictions,
            onset_tolerance_s=onset_tolerance_s,
            require_offset=require_offset,
        )
    else:
        labels = _active_labels(references, program_mode) | _active_labels(
            predictions, program_mode
        )
        matched = 0
        for label in labels:
            ref_subset = [note for note in references if _label(note, program_mode) == label]
            pred_subset = [note for note in predictions if _label(note, program_mode) == label]
            matched += _mir_eval_match_count(
                ref_subset,
                pred_subset,
                onset_tolerance_s=onset_tolerance_s,
                require_offset=require_offset,
            )

    precision = matched / len(predictions) if predictions else 0.0
    recall = matched / len(references) if references else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return MatchMetrics(
        reference_notes=len(references),
        predicted_notes=len(predictions),
        matched_notes=matched,
        precision=round(precision, 4),
        recall=round(recall, 4),
        f1=round(f1, 4),
    )


def _active_labels(notes: Iterable[NoteEvent], mode: ProgramMode) -> set[int]:
    labels: set[int] = set()
    for note in notes:
        label = _label(note, mode)
        if label is not None:
            labels.add(label)
    return labels


def instrument_detection(
    reference: Iterable[NoteEvent], predicted: Iterable[NoteEvent], *, mode: ProgramMode = "exact"
) -> MatchMetrics:
    """Score active program/drum labels independently of note timing."""

    reference_labels = _active_labels(reference, mode)
    predicted_labels = _active_labels(predicted, mode)
    matched = len(reference_labels & predicted_labels)
    precision = matched / len(predicted_labels) if predicted_labels else 0.0
    recall = matched / len(reference_labels) if reference_labels else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return MatchMetrics(
        reference_notes=len(reference_labels),
        predicted_notes=len(predicted_labels),
        matched_notes=matched,
        precision=round(precision, 4),
        recall=round(recall, 4),
        f1=round(f1, 4),
    )


def score_by_program(
    reference: list[NoteEvent],
    predicted: list[NoteEvent],
    *,
    mode: Literal["family", "exact"] = "exact",
) -> dict[str, dict[str, int | float]]:
    """Return label-specific onset metrics for every active reference/predicted label."""

    labels = _active_labels(reference, mode) | _active_labels(predicted, mode)
    results: dict[str, dict[str, int | float]] = {}
    for label in sorted(labels):
        ref_subset = [note for note in reference if _label(note, mode) == label]
        pred_subset = [note for note in predicted if _label(note, mode) == label]
        metrics = match_notes(ref_subset, pred_subset, program_mode=mode)
        name = "drums" if label == DRUM_LABEL else f"{mode}:{label}"
        results[name] = asdict(metrics)
    return results


def score_events(reference: list[NoteEvent], predicted: list[NoteEvent]) -> dict[str, object]:
    """Return complementary flat and instrument-aware AMT metrics."""

    family = asdict(match_notes(reference, predicted, program_mode="family"))
    family["by_program"] = score_by_program(reference, predicted, mode="family")
    exact = asdict(match_notes(reference, predicted, program_mode="exact"))
    exact["by_program"] = score_by_program(reference, predicted, mode="exact")
    return {
        "onset_flat": asdict(match_notes(reference, predicted)),
        "note_flat": asdict(match_notes(reference, predicted, require_offset=True)),
        "onset_program_family": family,
        "onset_program_exact": exact,
        "note_program_exact": asdict(
            match_notes(reference, predicted, program_mode="exact", require_offset=True)
        ),
        "instrument_detection_exact": asdict(
            instrument_detection(reference, predicted, mode="exact")
        ),
        "instrument_detection_family": asdict(
            instrument_detection(reference, predicted, mode="family")
        ),
    }
