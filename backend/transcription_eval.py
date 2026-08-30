"""Evaluation utilities for audio-to-MIDI experiment manifests.

The CLI/manifest contract and timing diagnostics live here; standard note
matching and precision/recall/F1 are delegated to the canonical mir_eval-backed
scorer in ``evaluation.transcription_metrics``.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path

from evaluation.transcription_metrics import Note, compute_note_metrics, match_notes


@dataclass(frozen=True)
class NoteEvent:
    pitch: int
    start: float
    end: float


@dataclass(frozen=True)
class NoteMetrics:
    reference_notes: int
    predicted_notes: int
    matched_notes: int
    extra_notes: int
    missing_notes: int
    precision: float
    recall: float
    f1: float
    mean_onset_error_ms: float | None
    mean_duration_error_ms: float | None


def _canonical(events: list[NoteEvent]) -> list[Note]:
    return [Note(pitch=event.pitch, start=event.start, end=event.end) for event in events]


def compare_events(
    reference: list[NoteEvent],
    predicted: list[NoteEvent],
    onset_tolerance_s: float = 0.05,
) -> NoteMetrics:
    """Compare normalized note events with the canonical mir_eval matcher."""
    reference_notes = _canonical(reference)
    predicted_notes = _canonical(predicted)
    metrics = compute_note_metrics(
        predicted_notes,
        reference_notes,
        onset_tolerance=onset_tolerance_s,
    )
    pairs, _, _ = match_notes(
        predicted_notes,
        reference_notes,
        onset_tolerance=onset_tolerance_s,
    )
    onset_errors = [abs(pred.start - ref.start) * 1000 for pred, ref in pairs]
    duration_errors = [
        abs((pred.end - pred.start) - (ref.end - ref.start)) * 1000 for pred, ref in pairs
    ]
    matched = metrics.onset_matched_count

    return NoteMetrics(
        reference_notes=len(reference),
        predicted_notes=len(predicted),
        matched_notes=matched,
        extra_notes=len(predicted) - matched,
        missing_notes=len(reference) - matched,
        precision=round(metrics.onset_precision, 4),
        recall=round(metrics.onset_recall, 4),
        f1=round(metrics.onset_f1, 4),
        mean_onset_error_ms=round(sum(onset_errors) / len(onset_errors), 2)
        if onset_errors
        else None,
        mean_duration_error_ms=round(sum(duration_errors) / len(duration_errors), 2)
        if duration_errors
        else None,
    )


def read_midi_events(path: Path) -> list[NoteEvent]:
    import pretty_midi

    midi = pretty_midi.PrettyMIDI(str(path))
    return [
        NoteEvent(pitch=note.pitch, start=round(note.start, 6), end=round(note.end, 6))
        for instrument in midi.instruments
        if not instrument.is_drum
        for note in instrument.notes
    ]


def evaluate_manifest(manifest_path: Path) -> dict[str, object]:
    """Evaluate JSON corpus entries with `reference_midi` and `predicted_midi`."""
    manifest = json.loads(manifest_path.read_text())
    root = manifest_path.parent
    entries = []
    for item in manifest["entries"]:
        metrics = compare_events(
            read_midi_events(root / item["reference_midi"]),
            read_midi_events(root / item["predicted_midi"]),
            float(item.get("onset_tolerance_s", 0.05)),
        )
        entries.append({"id": item["id"], "metrics": asdict(metrics)})
    return {"corpus": manifest.get("name", manifest_path.stem), "entries": entries}


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate a transcription corpus manifest")
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = evaluate_manifest(args.manifest)
    payload = json.dumps(result, indent=2) + "\n"
    if args.output:
        args.output.write_text(payload)
    else:
        print(payload, end="")


if __name__ == "__main__":
    main()
