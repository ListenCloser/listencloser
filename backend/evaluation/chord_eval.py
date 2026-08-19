"""Chord evaluation using mir_eval interval-based metrics.

Evaluates chord detection against GuitarSet JAMS annotations using
mir_eval.chord metrics (root, majmin, mirex, overseg, underseg, seg).

Usage:
    python -m evaluation.chord_eval
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import numpy as np

from evaluation.datasets.parsers import parse_guitarset_harmony, parse_guitarset_jams
from evaluation.engines.harmony import Music21HarmonyAdapter


def _chords_to_intervals(chords: list[dict[str, Any]]) -> tuple[np.ndarray, list[str]]:
    """Convert chord list to mir_eval format (intervals, labels).

    Returns:
        intervals: Nx2 array of [start, end] times in seconds
        labels: list of chord labels in mir_eval format (e.g., "C:maj", "G:min")
    """
    if not chords:
        return np.zeros((0, 2)), []

    intervals = np.array([[c["start"], c["end"]] for c in chords])
    labels = []
    for c in chords:
        root = c.get("root", "")
        quality = c.get("quality", "")

        # Normalize root to use # instead of - for sharps (mir_eval format)
        root = root.replace("-", "b")

        # Map to mir_eval format: Root:quality
        if quality in ("M", "maj", "major"):
            label = f"{root}:maj"
        elif quality in ("m", "min", "minor"):
            label = f"{root}:min"
        elif quality in ("dim", "diminished"):
            label = f"{root}:dim"
        elif quality in ("aug", "augmented"):
            label = f"{root}:aug"
        elif quality in ("7", "dom7", "dominant"):
            label = f"{root}:7"
        elif quality in ("maj7", "major7"):
            label = f"{root}:maj7"
        elif quality in ("min7", "m7", "minor7"):
            label = f"{root}:min7"
        elif quality in ("dim7", "diminished7"):
            label = f"{root}:dim7"
        elif quality in ("sus4",):
            label = f"{root}:sus4"
        elif quality in ("sus2",):
            label = f"{root}:sus2"
        elif quality in ("aug7",):
            label = f"{root}:aug7"
        elif quality in ("hdim7", "m7b5", "half-diminished"):
            label = f"{root}:hdim7"
        else:
            # Fallback: use raw quality, or X for unknown
            label = "X" if quality in ("other", "unknown", "") else f"{root}:{quality}"
        labels.append(label)

    return intervals, labels


def _merge_adjacent_identical(
    intervals: np.ndarray, labels: list[str]
) -> tuple[np.ndarray, list[str]]:
    """Merge adjacent chords with identical root+quality labels."""
    if len(intervals) <= 1:
        return intervals, labels

    merged_intervals = [intervals[0]]
    merged_labels = [labels[0]]

    for i in range(1, len(intervals)):
        if labels[i] == merged_labels[-1]:
            # Extend previous interval
            merged_intervals[-1] = [merged_intervals[-1][0], intervals[i][1]]
        else:
            merged_intervals.append(intervals[i])
            merged_labels.append(labels[i])

    return np.array(merged_intervals), merged_labels


def _merge_inversion_only(intervals: np.ndarray, labels: list[str]) -> tuple[np.ndarray, list[str]]:
    """Merge chords where only inversion differs (same root+quality)."""
    if len(intervals) <= 1:
        return intervals, labels

    def _root_quality(label: str) -> str:
        """Extract root:quality without inversion info."""
        parts = label.split(":")
        if len(parts) >= 2:
            return f"{parts[0]}:{parts[1]}"
        return label

    merged_intervals = [intervals[0]]
    merged_labels = [labels[0]]

    for i in range(1, len(intervals)):
        if _root_quality(labels[i]) == _root_quality(merged_labels[-1]):
            merged_intervals[-1] = [merged_intervals[-1][0], intervals[i][1]]
        else:
            merged_intervals.append(intervals[i])
            merged_labels.append(labels[i])

    return np.array(merged_intervals), merged_labels


def _suppress_short(
    intervals: np.ndarray, labels: list[str], min_duration: float = 0.1
) -> tuple[np.ndarray, list[str]]:
    """Remove chords shorter than min_duration seconds."""
    if len(intervals) == 0:
        return intervals, labels

    mask = (intervals[:, 1] - intervals[:, 0]) >= min_duration
    return intervals[mask], [labels[i] for i in range(len(labels)) if mask[i]]


def _beat_window_chord(
    intervals: np.ndarray,
    labels: list[str],
    beat_times: list[float],
) -> tuple[np.ndarray, list[str]]:
    """Choose representative chord per beat window."""
    if len(intervals) == 0 or len(beat_times) < 2:
        return intervals, labels

    result_intervals = []
    result_labels = []

    for i in range(len(beat_times) - 1):
        beat_start = beat_times[i]
        beat_end = beat_times[i + 1]

        # Find chords overlapping this beat window
        overlapping = []
        for _j, (iv, label) in enumerate(zip(intervals, labels, strict=False)):
            if iv[1] > beat_start and iv[0] < beat_end:
                # Compute overlap duration
                overlap_start = max(iv[0], beat_start)
                overlap_end = min(iv[1], beat_end)
                overlap_dur = overlap_end - overlap_start
                overlapping.append((overlap_dur, label))

        if overlapping:
            # Choose chord with longest overlap
            overlapping.sort(key=lambda x: -x[0])
            best_label = overlapping[0][1]
            result_intervals.append([beat_start, beat_end])
            result_labels.append(best_label)

    if not result_intervals:
        return np.zeros((0, 2)), []

    return np.array(result_intervals), result_labels


def evaluate_chords(
    pred_intervals: np.ndarray,
    pred_labels: list[str],
    ref_intervals: np.ndarray,
    ref_labels: list[str],
) -> dict[str, float]:
    """Evaluate predicted chords against reference using mir_eval.chord."""
    import mir_eval.chord

    # Ensure intervals are valid
    if len(pred_intervals) == 0:
        pred_intervals = np.zeros((0, 2))
    if len(ref_intervals) == 0:
        ref_intervals = np.zeros((0, 2))

    try:
        # mir_eval expects intervals sorted by start time
        if len(pred_intervals) > 0:
            sort_idx = np.argsort(pred_intervals[:, 0])
            pred_intervals = pred_intervals[sort_idx]
            pred_labels = [pred_labels[i] for i in sort_idx]
        if len(ref_intervals) > 0:
            sort_idx = np.argsort(ref_intervals[:, 0])
            ref_intervals = ref_intervals[sort_idx]
            ref_labels = [ref_labels[i] for i in sort_idx]

        # Use mir_eval.chord.evaluate which handles interval alignment
        scores = mir_eval.chord.evaluate(ref_intervals, ref_labels, pred_intervals, pred_labels)

        return {
            "root": float(scores.get("root", 0.0)),
            "majmin": float(scores.get("majmin", 0.0)),
            "mirex": float(scores.get("mirex", 0.0)),
            "overseg": float(scores.get("overseg", 0.0)),
            "underseg": float(scores.get("underseg", 0.0)),
            "seg": float(scores.get("seg", 0.0)),
        }

    except Exception as e:
        return {
            "root": 0.0,
            "majmin": 0.0,
            "mirex": 0.0,
            "overseg": 0.0,
            "underseg": 0.0,
            "seg": 0.0,
            "error": str(e),
        }


def run_evaluation() -> dict[str, Any]:
    """Run chord evaluation on GuitarSet clips."""

    guitarset_dir = Path("evaluation/.cache/guitarset")
    annotation_dir = guitarset_dir / "annotation"

    adapter = Music21HarmonyAdapter()
    results = []

    for jams_file in sorted(annotation_dir.glob("*.jams")):
        clip_id = jams_file.stem

        # Parse reference
        ref_data = parse_guitarset_harmony(jams_file.read_text())
        if not ref_data or not ref_data.get("chords"):
            continue

        ref_intervals, ref_labels = _chords_to_intervals(ref_data["chords"])

        # Parse note events for reference MIDI
        notes = parse_guitarset_jams(jams_file.read_text())
        if not notes:
            continue

        # Build reference MIDI from notes
        from evaluation.datasets.parsers import build_guitarset_reference_midi

        ref_midi = build_guitarset_reference_midi(notes)
        if not ref_midi:
            continue

        # Run production harmony
        try:
            result = adapter.analyze_harmony(ref_midi)
            pred_chords = result.get("chords", [])
        except Exception as e:
            print(f"{clip_id}: Error - {e}")
            continue

        pred_intervals, pred_labels = _chords_to_intervals(pred_chords)

        # Evaluate baseline
        baseline_scores = evaluate_chords(pred_intervals, pred_labels, ref_intervals, ref_labels)

        # Evaluate consolidation candidates
        candidates = {}

        # A. Merge adjacent identical
        merged_a_intervals, merged_a_labels = _merge_adjacent_identical(pred_intervals, pred_labels)
        candidates["merge_identical"] = evaluate_chords(
            merged_a_intervals, merged_a_labels, ref_intervals, ref_labels
        )
        candidates["merge_identical"]["event_count"] = len(merged_a_intervals)

        # B. Merge inversion-only
        merged_b_intervals, merged_b_labels = _merge_inversion_only(pred_intervals, pred_labels)
        candidates["merge_inversion"] = evaluate_chords(
            merged_b_intervals, merged_b_labels, ref_intervals, ref_labels
        )
        candidates["merge_inversion"]["event_count"] = len(merged_b_intervals)

        # C. Suppress short (< 0.1s)
        suppressed_c_intervals, suppressed_c_labels = _suppress_short(
            pred_intervals, pred_labels, 0.1
        )
        candidates["suppress_short_0.1"] = evaluate_chords(
            suppressed_c_intervals, suppressed_c_labels, ref_intervals, ref_labels
        )
        candidates["suppress_short_0.1"]["event_count"] = len(suppressed_c_intervals)

        # D. Suppress short (< 0.2s)
        suppressed_d_intervals, suppressed_d_labels = _suppress_short(
            pred_intervals, pred_labels, 0.2
        )
        candidates["suppress_short_0.2"] = evaluate_chords(
            suppressed_d_intervals, suppressed_d_labels, ref_intervals, ref_labels
        )
        candidates["suppress_short_0.2"]["event_count"] = len(suppressed_d_intervals)

        # E. Merge identical + suppress short
        merged_e_intervals, merged_e_labels = _merge_adjacent_identical(pred_intervals, pred_labels)
        suppressed_e_intervals, suppressed_e_labels = _suppress_short(
            merged_e_intervals, merged_e_labels, 0.1
        )
        candidates["merge_identical+suppress_0.1"] = evaluate_chords(
            suppressed_e_intervals, suppressed_e_labels, ref_intervals, ref_labels
        )
        candidates["merge_identical+suppress_0.1"]["event_count"] = len(suppressed_e_intervals)

        # F. Merge identical + merge inversion
        merged_f_intervals, merged_f_labels = _merge_adjacent_identical(pred_intervals, pred_labels)
        merged_f2_intervals, merged_f2_labels = _merge_inversion_only(
            merged_f_intervals, merged_f_labels
        )
        candidates["merge_identical+inversion"] = evaluate_chords(
            merged_f2_intervals, merged_f2_labels, ref_intervals, ref_labels
        )
        candidates["merge_identical+inversion"]["event_count"] = len(merged_f2_intervals)

        result_entry = {
            "clip_id": clip_id,
            "pred_count": len(pred_chords),
            "ref_count": len(ref_data["chords"]),
            "event_count_ratio": len(pred_chords) / len(ref_data["chords"])
            if ref_data["chords"]
            else 0,
            "baseline": baseline_scores,
            "candidates": candidates,
        }
        results.append(result_entry)

        print(
            f"{clip_id}: pred={len(pred_chords)}, ref={len(ref_data['chords'])}, "
            f"root={baseline_scores['root']:.3f}, majmin={baseline_scores['majmin']:.3f}, "
            f"mirex={baseline_scores['mirex']:.3f}"
        )

    return {"clips": results}


if __name__ == "__main__":
    results = run_evaluation()

    # Compute aggregates
    if results["clips"]:
        n = len(results["clips"])
        avg_root = sum(r["baseline"]["root"] for r in results["clips"]) / n
        avg_majmin = sum(r["baseline"]["majmin"] for r in results["clips"]) / n
        avg_mirex = sum(r["baseline"]["mirex"] for r in results["clips"]) / n
        avg_overseg = sum(r["baseline"]["overseg"] for r in results["clips"]) / n
        avg_underseg = sum(r["baseline"]["underseg"] for r in results["clips"]) / n
        avg_seg = sum(r["baseline"]["seg"] for r in results["clips"]) / n
        avg_ratio = sum(r["event_count_ratio"] for r in results["clips"]) / n

        print(f"\n=== AGGREGATE ({n} clips) ===")
        print(f"root:     {avg_root:.3f}")
        print(f"majmin:   {avg_majmin:.3f}")
        print(f"mirex:    {avg_mirex:.3f}")
        print(f"overseg:  {avg_overseg:.3f}")
        print(f"underseg: {avg_underseg:.3f}")
        print(f"seg:      {avg_seg:.3f}")
        print(f"event-count ratio: {avg_ratio:.2f}")

        # Print candidate aggregates
        print("\n=== CONSOLIDATION CANDIDATES ===")
        candidate_names = list(results["clips"][0]["candidates"].keys())
        for cand_name in candidate_names:
            avg_cand_root = sum(r["candidates"][cand_name]["root"] for r in results["clips"]) / n
            avg_cand_majmin = (
                sum(r["candidates"][cand_name]["majmin"] for r in results["clips"]) / n
            )
            avg_cand_mirex = sum(r["candidates"][cand_name]["mirex"] for r in results["clips"]) / n
            avg_cand_overseg = (
                sum(r["candidates"][cand_name]["overseg"] for r in results["clips"]) / n
            )
            avg_cand_ratio = (
                sum(
                    r["candidates"][cand_name]["event_count"] / r["ref_count"]
                    if r["ref_count"]
                    else 0
                    for r in results["clips"]
                )
                / n
            )
            print(
                f"{cand_name:35} "
                f"root={avg_cand_root:.3f} "
                f"majmin={avg_cand_majmin:.3f} "
                f"mirex={avg_cand_mirex:.3f} "
                f"overseg={avg_cand_overseg:.3f} "
                f"ratio={avg_cand_ratio:.2f}"
            )

    # Save results
    output_path = "evaluation/results/harmony/chord_mir_eval.json"
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nResults saved to {output_path}")
