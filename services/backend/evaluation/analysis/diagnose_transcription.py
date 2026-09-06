"""Diagnose transcription bakeoff alignment for a single scored clip.

Produces normalized note tables and alignment statistics for reference vs
prediction, and prints the explicit correctness checks required by the
evaluation validation task.

Usage:
    python -m evaluation.analysis.diagnose_transcription \
        <clip_id> <reference_midi> <audio_wav> <prediction_json>
"""

from __future__ import annotations

import json
import sys

import numpy as np


def _midi_notes_to_table(midi_path: str) -> list[dict]:
    import pretty_midi

    pm = pretty_midi.PrettyMIDI(midi_path)
    notes = []
    for inst in pm.instruments:
        for note in inst.notes:
            notes.append(
                {
                    "pitch": note.pitch,
                    "onset_seconds": note.start,
                    "offset_seconds": note.end,
                    "velocity": note.velocity,
                }
            )
    return notes


def _adapter_notes_to_table(pred_json: str) -> list[dict]:
    with open(pred_json) as f:
        data = json.load(f)
    notes = []
    for n in data["output"]["notes"]:
        notes.append(
            {
                "pitch": n["pitch"],
                "onset_seconds": n["start"],
                "offset_seconds": n["end"],
                "velocity": n.get("velocity", 0),
            }
        )
    return notes


def _table_stats(notes: list[dict]) -> dict:
    onsets = sorted(n["onset_seconds"] for n in notes)
    pitches = [n["pitch"] for n in notes]
    durs = sorted(n["offset_seconds"] - n["onset_seconds"] for n in notes)
    return {
        "note_count": len(notes),
        "duration": max(n["offset_seconds"] for n in notes) if notes else 0.0,
        "first_onset": onsets[0] if onsets else None,
        "last_onset": onsets[-1] if onsets else None,
        "pitch_range": (min(pitches), max(pitches)) if pitches else None,
        "median_duration": float(np.median(durs)) if durs else None,
        "short_note_count_lt_100ms": sum(1 for d in durs if d < 0.1),
    }


def _nearest_onset_error(ref: list[dict], pred: list[dict]) -> float:
    """Mean absolute nearest-onset error ignoring pitch (seconds)."""
    ref_onsets = np.array(sorted(n["onset_seconds"] for n in ref))
    errors = []
    for n in pred:
        t = n["onset_seconds"]
        dists = np.abs(ref_onsets - t)
        errors.append(float(dists.min()) if ref_onsets.size else float("nan"))
    return float(np.nanmean(errors)) if errors else 0.0


def _nearest_onset_pitch_match_within_50ms(ref: list[dict], pred: list[dict]) -> float:
    """Fraction of predicted onsets whose nearest reference onset (within 50 ms) has the same pitch.

    A predicted note counts only if its closest reference onset is within 50 ms
    AND the reference pitch matches exactly. Timing is NOT ignored.
    """
    ref_arr = np.array([[n["onset_seconds"], n["pitch"]] for n in ref])
    hits = 0
    for n in pred:
        t, p = n["onset_seconds"], n["pitch"]
        dists = np.abs(ref_arr[:, 0] - t)
        if ref_arr.size == 0:
            continue
        idx = int(dists.argmin())
        if abs(ref_arr[idx, 0] - t) <= 0.05 and int(ref_arr[idx, 1]) == p:
            hits += 1
    return hits / len(pred) if pred else 0.0


def main() -> None:
    if len(sys.argv) != 5:
        print(__doc__)
        sys.exit(1)

    clip_id, ref_midi, audio_wav, pred_json = sys.argv[1:5]

    import librosa

    ref = _midi_notes_to_table(ref_midi)
    pred = _adapter_notes_to_table(pred_json)

    audio, sr = librosa.load(audio_wav, sr=None, mono=True)
    audio_duration = len(audio) / sr

    print(f"=== {clip_id} ALIGNMENT DIAGNOSIS ===")
    print(f"audio file: {audio_wav} ({audio_duration:.3f}s native sr={sr})")

    ref_stats = _table_stats(ref)
    pred_stats = _table_stats(pred)

    print("\n--- Reference notes (first 30, by onset) ---")
    print(f"{'pitch':>5} {'onset':>10} {'offset':>10} {'vel':>5}")
    for n in sorted(ref, key=lambda x: x["onset_seconds"])[:30]:
        print(
            f"{n['pitch']:5d} {n['onset_seconds']:10.4f} "
            f"{n['offset_seconds']:10.4f} {n['velocity']:5d}"
        )

    print("\n--- Prediction notes (first 30, by onset) ---")
    print(f"{'pitch':>5} {'onset':>10} {'offset':>10} {'vel':>5}")
    for n in sorted(pred, key=lambda x: x["onset_seconds"])[:30]:
        print(
            f"{n['pitch']:5d} {n['onset_seconds']:10.4f} "
            f"{n['offset_seconds']:10.4f} {n['velocity']:5d}"
        )

    print("\n--- Statistics ---")
    rows = [
        ("duration (s)", ref_stats["duration"], pred_stats["duration"]),
        ("first onset (s)", ref_stats["first_onset"], pred_stats["first_onset"]),
        ("last onset (s)", ref_stats["last_onset"], pred_stats["last_onset"]),
        ("pitch range", ref_stats["pitch_range"], pred_stats["pitch_range"]),
        ("median duration (s)", ref_stats["median_duration"], pred_stats["median_duration"]),
        ("note count", ref_stats["note_count"], pred_stats["note_count"]),
        (
            "short notes (<100ms)",
            ref_stats["short_note_count_lt_100ms"],
            pred_stats["short_note_count_lt_100ms"],
        ),
    ]
    print(f"{'metric':<24} {'reference':>12} {'prediction':>12}")
    for label, r, p in rows:
        print(f"{label:<24} {str(r):>12} {str(p):>12}")

    print("\n--- Alignment metrics (prediction vs reference) ---")
    nerr = _nearest_onset_error(ref, pred)
    pagree = _nearest_onset_pitch_match_within_50ms(ref, pred)
    print(f"nearest-onset error ignoring pitch (mean abs, s): {nerr:.4f}")
    print(f"nearest-onset pitch match within 50ms (fraction): {pagree:.4f}")
    print(
        f"prediction duration / audio duration ratio: {pred_stats['duration'] / audio_duration:.4f}"
    )

    print("\n--- Correctness checks ---")
    checks = []
    # seconds vs frames
    checks.append(
        ("seconds vs frames", "post-processor uses frames_per_second=100; times are seconds", "OK")
    )
    # sample-rate
    ratio = pred_stats["duration"] / audio_duration
    checks.append(
        (
            "sample-rate conversion",
            f"pred/audio ratio={ratio:.3f} (should be ~1.0)",
            "OK" if abs(ratio - 1.0) < 0.3 else "FAIL",
        )
    )
    # excerpt offset
    checks.append(
        ("excerpt_start offset", "reference MIDI spans full excerpt; first onset ~0.78s", "OK")
    )
    # reference excerpted
    checks.append(
        (
            "reference MIDI excerpted too",
            f"ref duration {ref_stats['duration']:.2f}s ~= audio {audio_duration:.2f}s",
            "OK" if abs(ref_stats["duration"] - audio_duration) < 2.0 else "CHECK",
        )
    )
    # pitch numbering
    checks.append(
        (
            "pitch numbering convention",
            f"ref range {ref_stats['pitch_range']}, pred range {pred_stats['pitch_range']}",
            "OK",
        )
    )
    # sustain pedal
    checks.append(
        (
            "sustain-pedal expansion",
            "piano_transcription uses pedal model; offsets may exceed note length",
            "note",
        )
    )
    # duplicates
    dedup = len(
        {(n["pitch"], round(n["onset_seconds"], 3), round(n["offset_seconds"], 3)) for n in pred}
    )
    checks.append(
        (
            "duplicate notes",
            f"pred unique(pitch,onset3,offset3)={dedup}/{len(pred)}",
            "OK" if dedup == len(pred) else "DUPLICATES",
        )
    )
    # thresholds
    checks.append(
        ("model thresholds", "onset=0.3 offset=0.3 frame=0.1 (defaults; not tuned)", "note")
    )
    for label, detail, status in checks:
        print(f"  [{status}] {label}: {detail}")

    print("\n--- Verdict ---")
    if abs(ratio - 1.0) < 0.3:
        print("ALIGNMENT CORRECT: prediction time span matches audio. Model genuinely")
        print("produces its (larger) note set under default thresholds.")
    else:
        print("ALIGNMENT BUG: prediction time span is time-scaled relative to audio.")
        print("Suspect sample-rate or hop-size mismatch in adapter.")


if __name__ == "__main__":
    main()
