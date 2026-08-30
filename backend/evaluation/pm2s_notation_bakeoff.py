"""Isolated current-vs-PM2S notation bakeoff.

This evaluator intentionally sits beside the production notation engine. PM2S is
executed in a separate Python environment so its research-era dependencies and
runtime-downloaded checkpoints can never become backend dependencies.

The comparison keeps transcription out of the question: the exact same
performance MIDI bytes are given to the current notation path and to PM2S.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

PM2S_REPOSITORY = "https://github.com/cheriell/PM2S"
PM2S_SOURCE_SHA = "9586f91cd16aaa50dbb82f720f6a34a3e0186f47"
PM2S_WEIGHT_RECORD = "https://zenodo.org/records/10520196"
PM2S_WEIGHT_URLS = (
    "https://zenodo.org/records/10520196/files/beat.pth?download=1",
    "https://zenodo.org/records/10520196/files/hand_part.pth?download=1",
    "https://zenodo.org/records/10520196/files/quantisation.pth?download=1",
    "https://zenodo.org/records/10520196/files/time_signature.pth?download=1",
    "https://zenodo.org/records/10520196/files/key_signature.pth?download=1",
)

_PM2S_RUNNER = r"""
import pathlib
import sys

repo, input_midi, output_midi = sys.argv[1:4]
sys.path.insert(0, repo)
from pm2s.pm2s import CRNNJointPM2S

model = CRNNJointPM2S()
model.convert(
    input_midi,
    output_midi,
    include_time_signature=True,
    include_key_signature=True,
)
if not pathlib.Path(output_midi).is_file():
    raise RuntimeError("PM2S did not produce score MIDI")
"""


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def build_pm2s_command(
    pm2s_python: str,
    pm2s_repo: str,
    input_midi: str,
    output_midi: str,
) -> list[str]:
    """Build the isolated PM2S command without importing PM2S in this process."""
    return [
        pm2s_python,
        "-c",
        _PM2S_RUNNER,
        pm2s_repo,
        input_midi,
        output_midi,
    ]


def validate_pm2s_checkout(pm2s_repo: str) -> str:
    """Fail closed unless the candidate checkout is exactly the reviewed SHA."""
    proc = subprocess.run(
        ["git", "-C", pm2s_repo, "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    )
    sha = proc.stdout.strip()
    if sha != PM2S_SOURCE_SHA:
        raise RuntimeError(
            f"PM2S checkout must be {PM2S_SOURCE_SHA}; got {sha or '<empty>'}"
        )
    return sha


def _all_notes(midi_bytes: bytes) -> list[Any]:
    import pretty_midi

    midi = pretty_midi.PrettyMIDI(io.BytesIO(midi_bytes))
    return [
        note
        for instrument in midi.instruments
        if not instrument.is_drum
        for note in instrument.notes
    ]


def diagnose_midi(midi_bytes: bytes) -> dict[str, int | float | None]:
    """Structural score-MIDI diagnostics that do not require a reference score."""
    notes = sorted(_all_notes(midi_bytes), key=lambda n: (n.start, n.pitch, n.end))
    durations = [max(0.0, float(note.end - note.start)) for note in notes]

    by_pitch: dict[int, list[Any]] = {}
    for note in notes:
        by_pitch.setdefault(int(note.pitch), []).append(note)
    same_pitch_overlaps = 0
    for pitch_notes in by_pitch.values():
        pitch_notes.sort(key=lambda n: (n.start, n.end))
        previous_end = -1.0
        for note in pitch_notes:
            if note.start < previous_end - 1e-6:
                same_pitch_overlaps += 1
            previous_end = max(previous_end, float(note.end))

    events: list[tuple[float, int]] = []
    for note in notes:
        events.append((float(note.start), 1))
        events.append((float(note.end), -1))
    # Ends before starts at the same instant: touching notes are not simultaneous.
    events.sort(key=lambda item: (item[0], item[1]))
    active = 0
    max_polyphony = 0
    for _, delta in events:
        active += delta
        max_polyphony = max(max_polyphony, active)

    rounded_durations = {round(value, 3) for value in durations if value > 0}
    return {
        "note_count": len(notes),
        "same_pitch_overlap_count": same_pitch_overlaps,
        "max_polyphony": max_polyphony,
        "distinct_duration_count_1ms": len(rounded_durations),
        "duration_min_seconds": round(min(durations), 4) if durations else None,
        "duration_max_seconds": round(max(durations), 4) if durations else None,
    }


def reference_grid_from_midi(
    midi_bytes: bytes,
    *,
    start: float | None = None,
    end: float | None = None,
) -> tuple[list[float], list[float]]:
    """Derive a best-case beat/downbeat grid from the source performance MIDI.

    When an excerpt window is supplied, the grid is derived *before* MIDI
    excerpting, then clipped and rebased. This preserves MAESTRO's source tempo
    map instead of pretending the excerpt has one fixed tempo.
    """
    if (start is None) != (end is None):
        raise ValueError("start and end must be supplied together")
    if start is not None and end is not None and (start < 0 or end <= start):
        raise ValueError("grid slice requires 0 <= start < end")

    import pretty_midi

    midi = pretty_midi.PrettyMIDI(io.BytesIO(midi_bytes))
    beats = [float(value) for value in midi.get_beats()]
    downbeats = [float(value) for value in midi.get_downbeats()]
    if len(beats) < 2:
        total_time = float(midi.get_end_time())
        _, tempi = midi.get_tempo_changes()
        bpm = float(tempi[0]) if len(tempi) else 120.0
        interval = 60.0 / max(bpm, 1e-6)
        beats = []
        value = 0.0
        while value <= total_time + interval:
            beats.append(value)
            value += interval

    if start is None or end is None:
        return beats, downbeats

    epsilon = 1e-6
    excerpt_beats = [
        value - start for value in beats if start - epsilon <= value <= end + epsilon
    ]
    excerpt_downbeats = [
        value - start
        for value in downbeats
        if start - epsilon <= value <= end + epsilon
    ]
    if len(excerpt_beats) < 2:
        raise ValueError("reference MIDI excerpt contains fewer than two beats")
    return excerpt_beats, excerpt_downbeats


def slice_performance_midi(midi_bytes: bytes, start: float, end: float) -> bytes:
    """Create one bounded performance-MIDI excerpt with time rebased to zero."""
    if start < 0 or end <= start:
        raise ValueError("slice requires 0 <= start < end")

    import pretty_midi

    source = pretty_midi.PrettyMIDI(io.BytesIO(midi_bytes))
    _, tempi = source.get_tempo_changes()
    initial_tempo = float(tempi[0]) if len(tempi) else 120.0
    sliced = pretty_midi.PrettyMIDI(
        initial_tempo=initial_tempo,
        resolution=source.resolution,
    )

    for instrument in source.instruments:
        if instrument.is_drum:
            continue
        target = pretty_midi.Instrument(
            program=instrument.program,
            is_drum=False,
            name=instrument.name,
        )
        for note in instrument.notes:
            overlap_start = max(float(note.start), start)
            overlap_end = min(float(note.end), end)
            if overlap_end <= overlap_start:
                continue
            target.notes.append(
                pretty_midi.Note(
                    velocity=int(note.velocity),
                    pitch=int(note.pitch),
                    start=overlap_start - start,
                    end=overlap_end - start,
                )
            )
        if target.notes:
            sliced.instruments.append(target)

    if not sliced.instruments:
        raise ValueError("slice contains no pitched notes")

    output = io.BytesIO()
    sliced.write(output)
    return output.getvalue()


def _current_score(
    performance_midi: bytes,
    *,
    reference_grid: tuple[list[float], list[float]] | None = None,
) -> dict[str, Any]:
    from evaluation.notation_metrics import diagnose_musicxml
    from music_features import notation_with_engine

    beats, downbeats = reference_grid or reference_grid_from_midi(performance_midi)
    started = time.perf_counter()
    result = notation_with_engine(
        performance_midi,
        beats,
        adaptive=True,
        downbeats=downbeats,
        notation_ready=True,
        piano_grand_staff=True,
    )
    runtime = time.perf_counter() - started
    notation_midi = result["notation_midi"]
    musicxml = result["musicxml"]
    return {
        "status": "measured",
        "grid_source": "source_reference_performance_midi_best_case",
        "grid_beat_count": len(beats),
        "grid_downbeat_count": len(downbeats),
        "runtime_seconds": round(runtime, 4),
        "notation_midi_sha256": sha256_bytes(notation_midi),
        "midi_diagnostics": diagnose_midi(notation_midi),
        "musicxml_diagnostics": diagnose_musicxml(musicxml).to_dict(),
        "quantization_report": result.get("quantization_report"),
        "provenance": result.get("provenance"),
    }


def _checkpoint_provenance(pm2s_repo: str) -> list[dict[str, str]]:
    repo = Path(pm2s_repo).resolve()
    rows: list[dict[str, str]] = []
    for path in sorted(repo.rglob("*.pth")):
        rows.append(
            {
                "path": str(path.relative_to(repo)),
                "sha256": sha256_file(path),
            }
        )
    return rows


def _pm2s_score(
    performance_midi: bytes,
    *,
    pm2s_python: str,
    pm2s_repo: str,
) -> dict[str, Any]:
    from evaluation.notation_metrics import diagnose_musicxml
    from music_features import convert_format

    validate_pm2s_checkout(pm2s_repo)
    with tempfile.TemporaryDirectory() as temp_dir:
        input_path = Path(temp_dir) / "performance.mid"
        output_path = Path(temp_dir) / "score.mid"
        input_path.write_bytes(performance_midi)

        started = time.perf_counter()
        proc = subprocess.run(
            build_pm2s_command(
                pm2s_python,
                pm2s_repo,
                str(input_path),
                str(output_path),
            ),
            check=True,
            capture_output=True,
            text=True,
            timeout=900,
        )
        runtime = time.perf_counter() - started
        score_midi = output_path.read_bytes()

    # This conversion is only a common diagnostic surface. It is not presented
    # as PM2S's own engraving layer and does not alter the score MIDI metrics.
    musicxml = convert_format(
        score_midi,
        "midi",
        "musicxml",
        notation_ready=True,
        piano_grand_staff=False,
    )
    return {
        "status": "measured",
        "grid_source": "pm2s_internal_neural_beat_tracking",
        "runtime_seconds": round(runtime, 4),
        "notation_midi_sha256": sha256_bytes(score_midi),
        "midi_diagnostics": diagnose_midi(score_midi),
        "musicxml_diagnostics": diagnose_musicxml(musicxml).to_dict(),
        "conversion_surface": "hello-ai music21 MIDI->MusicXML; diagnostics only",
        "stdout_tail": proc.stdout[-4000:],
        "stderr_tail": proc.stderr[-4000:],
        "checkpoints": _checkpoint_provenance(pm2s_repo),
    }


def evaluate_pair(
    performance_midi: bytes,
    *,
    clip_id: str,
    pm2s_python: str,
    pm2s_repo: str,
    product_baseline_sha: str | None = None,
    current_reference_grid: tuple[list[float], list[float]] | None = None,
) -> dict[str, Any]:
    """Evaluate the same MIDI through current notation and isolated PM2S."""
    input_sha = sha256_bytes(performance_midi)
    current = _current_score(
        performance_midi,
        reference_grid=current_reference_grid,
    )

    try:
        candidate = _pm2s_score(
            performance_midi,
            pm2s_python=pm2s_python,
            pm2s_repo=pm2s_repo,
        )
    except Exception as exc:
        candidate = {
            "status": "unavailable",
            "error": f"{type(exc).__name__}: {exc}",
            "grid_source": "pm2s_internal_neural_beat_tracking",
            "checkpoints": _checkpoint_provenance(pm2s_repo)
            if Path(pm2s_repo).exists()
            else [],
        }

    return {
        "evaluation_id": "performance_midi_to_readable_score_pm2s_v1",
        "clip_id": clip_id,
        "input": {
            "sha256": input_sha,
            "note_count": diagnose_midi(performance_midi)["note_count"],
            "transcription_in_scope": False,
        },
        "current": current,
        "pm2s": candidate,
        "provenance": {
            "product_baseline_sha": product_baseline_sha,
            "pm2s_repository": PM2S_REPOSITORY,
            "pm2s_source_sha": PM2S_SOURCE_SHA,
            "pm2s_source_license": "MIT",
            "pm2s_checkpoint_record": PM2S_WEIGHT_RECORD,
            "pm2s_checkpoint_urls": list(PM2S_WEIGHT_URLS),
            "pm2s_checkpoint_rights": "unverified; research/evaluation only",
            "interpretation": (
                "Same excerpted performance MIDI is used for both paths. Current "
                "receives a best-case beat/downbeat grid clipped and rebased from "
                "the original source performance MIDI before excerpting; PM2S "
                "predicts its own grid. No transcription/routing change is tested."
            ),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compare current MIDI->Score interpretation against isolated PM2S"
    )
    parser.add_argument("--input-midi", required=True)
    parser.add_argument("--clip-id", required=True)
    parser.add_argument("--pm2s-python", required=True)
    parser.add_argument("--pm2s-repo", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--start", type=float)
    parser.add_argument("--end", type=float)
    parser.add_argument("--product-baseline-sha")
    parser.add_argument(
        "--require-pm2s",
        action="store_true",
        help="exit nonzero when PM2S cannot produce a candidate",
    )
    args = parser.parse_args()

    source_midi_bytes = Path(args.input_midi).read_bytes()
    midi_bytes = source_midi_bytes
    current_reference_grid = None
    if args.start is not None or args.end is not None:
        if args.start is None or args.end is None:
            parser.error("--start and --end must be supplied together")
        current_reference_grid = reference_grid_from_midi(
            source_midi_bytes,
            start=args.start,
            end=args.end,
        )
        midi_bytes = slice_performance_midi(
            source_midi_bytes,
            args.start,
            args.end,
        )

    result = evaluate_pair(
        midi_bytes,
        clip_id=args.clip_id,
        pm2s_python=args.pm2s_python,
        pm2s_repo=args.pm2s_repo,
        product_baseline_sha=args.product_baseline_sha,
        current_reference_grid=current_reference_grid,
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + "\n")

    if args.require_pm2s and result["pm2s"]["status"] != "measured":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
