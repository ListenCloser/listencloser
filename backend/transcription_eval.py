"""Evaluation utilities for audio-to-MIDI experiments.

This module deliberately has no model dependency.  It compares normalized note
events, so a Basic Pitch baseline, cleanup profile, or future AMT model can be
measured with the same corpus and acceptance thresholds.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path


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


def compare_events(
    reference: list[NoteEvent],
    predicted: list[NoteEvent],
    onset_tolerance_s: float = 0.05,
) -> NoteMetrics:
    """Greedily match same-pitch notes within an explicit onset tolerance.

    Matching is intentionally deterministic and readable. It is a product
    regression signal, not a replacement for a research benchmark such as
    mir_eval; the corpus can later add those stricter metrics without changing
    the artifact contract.
    """
    unmatched = set(range(len(reference)))
    pairs: list[tuple[NoteEvent, NoteEvent]] = []
    for candidate in sorted(predicted, key=lambda note: (note.start, note.pitch, note.end)):
        options = [
            index
            for index in unmatched
            if reference[index].pitch == candidate.pitch
            and abs(reference[index].start - candidate.start) <= onset_tolerance_s
        ]
        if not options:
            continue
        best = min(
            options,
            key=lambda index: (abs(reference[index].start - candidate.start), reference[index].end),
        )
        unmatched.remove(best)
        pairs.append((reference[best], candidate))

    matched = len(pairs)
    precision = matched / len(predicted) if predicted else 0.0
    recall = matched / len(reference) if reference else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    onset_errors = [abs(actual.start - found.start) * 1000 for actual, found in pairs]
    duration_errors = [
        abs((actual.end - actual.start) - (found.end - found.start)) * 1000
        for actual, found in pairs
    ]
    return NoteMetrics(
        reference_notes=len(reference),
        predicted_notes=len(predicted),
        matched_notes=matched,
        extra_notes=len(predicted) - matched,
        missing_notes=len(reference) - matched,
        precision=round(precision, 4),
        recall=round(recall, 4),
        f1=round(f1, 4),
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
