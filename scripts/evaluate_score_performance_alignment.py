#!/usr/bin/env python3
"""Issue #1083 isolated Partitura/Parangonar evaluation.

This script intentionally evaluates the OSS matcher outside production wiring.  The
``eval-*-sha256`` identifiers below are deterministic content identities for the
fixture slices; they are NOT ListenCloser Version IDs and confer no product
authority.
"""

from __future__ import annotations

import hashlib
import importlib.metadata
import importlib.resources
import json
import resource
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import numpy as np
import partitura as pt
from parangonar import DualDTWNoteMatcher, fscore_alignments


def _scalar(value: Any) -> Any:
    return value.item() if isinstance(value, np.generic) else value


def array_identity(kind: str, array: np.ndarray) -> str:
    h = hashlib.sha256()
    h.update(repr(array.dtype.descr).encode())
    h.update(np.ascontiguousarray(array).tobytes())
    return f"eval-{kind}-sha256:{h.hexdigest()}"


def filter_alignment(
    alignment: list[dict[str, Any]], score_ids: set[Any], performance_ids: set[Any]
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for record in alignment:
        label = record["label"]
        sid = record.get("score_id")
        pid = record.get("performance_id")
        if label == "match" and sid in score_ids and pid in performance_ids:
            out.append(record)
        elif label == "deletion" and sid in score_ids:
            out.append(record)
        elif label == "insertion" and pid in performance_ids:
            out.append(record)
    return out


def matched_performance_ids(
    alignment: list[dict[str, Any]], score_ids: set[Any]
) -> set[Any]:
    return {
        record["performance_id"]
        for record in alignment
        if record["label"] == "match" and record.get("score_id") in score_ids
    }


def timing_summary(
    prediction: list[dict[str, Any]], score: np.ndarray, performance: np.ndarray
) -> dict[str, Any]:
    score_by_id = {row["id"]: row for row in score}
    perf_by_id = {row["id"]: row for row in performance}
    pairs: list[tuple[float, float]] = []
    for record in prediction:
        if record["label"] != "match":
            continue
        srow = score_by_id.get(record["score_id"])
        prow = perf_by_id.get(record["performance_id"])
        if srow is not None and prow is not None:
            pairs.append((float(srow["onset_beat"]), float(prow["onset_sec"])))
    if len(pairs) < 2:
        return {"anchors": len(pairs), "linear_residual_sec": None}
    xy = np.asarray(pairs, dtype=float)
    slope, intercept = np.polyfit(xy[:, 0], xy[:, 1], 1)
    residual = np.abs(xy[:, 1] - (slope * xy[:, 0] + intercept))
    return {
        "anchors": len(pairs),
        "seconds_per_beat_global_fit": float(slope),
        "linear_residual_sec": {
            "p50": float(np.quantile(residual, 0.50)),
            "p95": float(np.quantile(residual, 0.95)),
            "max": float(np.max(residual)),
        },
    }


def alignment_shape(prediction: list[dict[str, Any]]) -> dict[str, Any]:
    labels = Counter(record["label"] for record in prediction)
    score_to_perf: defaultdict[Any, list[Any]] = defaultdict(list)
    perf_to_score: defaultdict[Any, list[Any]] = defaultdict(list)
    for record in prediction:
        if record["label"] == "match":
            score_to_perf[record["score_id"]].append(record["performance_id"])
            perf_to_score[record["performance_id"]].append(record["score_id"])
    one_to_many = sum(len(values) > 1 for values in score_to_perf.values())
    many_to_one = sum(len(values) > 1 for values in perf_to_score.values())
    return {
        "matched": labels["match"],
        "score_only": labels["deletion"],
        "performance_only": labels["insertion"],
        "one_to_many_score_events": one_to_many,
        "many_to_one_performance_events": many_to_one,
    }


def run_case(
    name: str,
    score: np.ndarray,
    performance: np.ndarray,
    ground_truth: list[dict[str, Any]] | None,
    *,
    score_part: Any | None = None,
    process_ornaments: bool = False,
) -> dict[str, Any]:
    matcher = DualDTWNoteMatcher()
    started = time.perf_counter()
    try:
        prediction = matcher(
            score,
            performance,
            process_ornaments=process_ornaments,
            score_part=score_part,
        )
        elapsed = time.perf_counter() - started
        result: dict[str, Any] = {
            "case": name,
            "score_version": array_identity("score", score),
            "performance_version": array_identity("performance", performance),
            "score_notes": len(score),
            "performance_notes": len(performance),
            "matcher": "DualDTWNoteMatcher",
            "parameters": {"process_ornaments": process_ornaments},
            "runtime_sec": elapsed,
            "failure": None,
            **alignment_shape(prediction),
            "timing": timing_summary(prediction, score, performance),
        }
        if ground_truth is not None:
            precision, recall, f_score = fscore_alignments(
                prediction, ground_truth, "match"
            )
            result["ground_truth_match"] = {
                "precision": float(precision),
                "recall": float(recall),
                "f1": float(f_score),
                "ground_truth_counts": alignment_shape(ground_truth),
            }
        return result
    except Exception as exc:  # evaluator records matcher failure instead of hiding it
        return {
            "case": name,
            "score_version": array_identity("score", score),
            "performance_version": array_identity("performance", performance),
            "score_notes": len(score),
            "performance_notes": len(performance),
            "matcher": "DualDTWNoteMatcher",
            "parameters": {"process_ornaments": process_ornaments},
            "runtime_sec": time.perf_counter() - started,
            "failure": {"type": type(exc).__name__, "message": str(exc)},
        }


def main() -> None:
    package_root = Path(importlib.resources.files("parangonar"))
    fixture = package_root / "assets" / "mozart_k265_var1.match"
    perf, ground_truth, score = pt.load_match(str(fixture), create_score=True)
    score_na = score.note_array(include_grace_notes=True)
    perf_na = perf.note_array()

    # Clean/simple excerpt: first 32 notated events and only their GT-matched
    # performed notes. This isolates the basic one-to-one relation on real data.
    simple_score = score_na[:32].copy()
    simple_score_ids = set(simple_score["id"])
    simple_perf_ids = matched_performance_ids(ground_truth, simple_score_ids)
    simple_perf = perf_na[np.isin(perf_na["id"], list(simple_perf_ids))].copy()
    simple_gt = filter_alignment(ground_truth, simple_score_ids, set(simple_perf["id"]))

    # Non-trivial chord window: locate the most simultaneous score onset and use
    # a bounded real passage around it.  This tests dense note grouping without
    # inventing synthetic music.
    onsets, counts = np.unique(score_na["onset_beat"], return_counts=True)
    chord_onset = float(onsets[int(np.argmax(counts))])
    chord_mask = np.abs(score_na["onset_beat"].astype(float) - chord_onset) <= 1.0
    chord_score = score_na[chord_mask].copy()
    chord_score_ids = set(chord_score["id"])
    chord_perf_ids = matched_performance_ids(ground_truth, chord_score_ids)
    chord_perf = perf_na[np.isin(perf_na["id"], list(chord_perf_ids))].copy()
    chord_gt = filter_alignment(ground_truth, chord_score_ids, set(chord_perf["id"]))

    # Deliberately corrupted control: preserve event IDs/timing but transpose the
    # simple performance by a tritone.  A trustworthy matcher should not silently
    # report ordinary exact coverage.
    corrupted_perf = simple_perf.copy()
    corrupted_perf["pitch"] = np.clip(corrupted_perf["pitch"].astype(int) + 6, 0, 127)

    cases = [
        run_case("clean_simple_real", simple_score, simple_perf, simple_gt),
        run_case(
            "expressive_full_real",
            score_na.copy(),
            perf_na.copy(),
            ground_truth,
            score_part=score[0],
            process_ornaments=True,
        ),
        run_case("dense_chord_real", chord_score, chord_perf, chord_gt),
        run_case("corrupted_pitch_control", simple_score, corrupted_perf, simple_gt),
    ]

    # Explicit degenerate-input failure characterization.
    empty_score = score_na[:0].copy()
    malformed_case = run_case("empty_score_control", empty_score, simple_perf, None)
    cases.append(malformed_case)

    asset_sizes = {
        path.name: path.stat().st_size
        for path in (package_root / "assets").iterdir()
        if path.is_file()
    }
    report = {
        "evaluation": "github-issue-1083",
        "authority_note": (
            "eval-*-sha256 identities are evaluator-only immutable content digests, "
            "not ListenCloser Version IDs and not representation authority"
        ),
        "python": sys.version,
        "packages": {
            name: importlib.metadata.version(name)
            for name in [
                "numpy",
                "scipy",
                "music21",
                "pretty-midi",
                "partitura",
                "parangonar",
            ]
        },
        "fixture": {
            "source": "parangonar/assets/mozart_k265_var1.match",
            "sha256": hashlib.sha256(fixture.read_bytes()).hexdigest(),
            "score_notes": len(score_na),
            "performance_notes": len(perf_na),
            "ground_truth_counts": alignment_shape(ground_truth),
            "max_simultaneous_score_notes": int(np.max(counts)),
            "dense_chord_onset_beat": chord_onset,
        },
        "parangonar_packaged_asset_sizes_bytes": asset_sizes,
        "cases": cases,
        "max_rss_kib": int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss),
    }
    print(json.dumps(report, indent=2, sort_keys=True, default=_scalar))


if __name__ == "__main__":
    main()
