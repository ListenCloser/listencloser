"""Run the #848 measured-change discovery control on real audio files.

This runner is evaluation-only. It records literal candidate boundaries and
production-owned before/after measurements; it does not assign section/drop or
importance labels.
"""

from __future__ import annotations

import argparse
import json
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from backend.evaluation.analysis_v3.perceptual.change_candidates import (
    ChangeDiscoveryResult,
    discover_measured_change_candidates,
)
from perceptual_evidence import extract_perceptual_evidence_from_bytes


def _package_version(name: str) -> str:
    try:
        return version(name)
    except PackageNotFoundError:
        return "unknown"


def _format(path: Path) -> str:
    suffix = path.suffix.lstrip(".").lower()
    return suffix or "wav"


def _expected_summary(
    result: ChangeDiscoveryResult,
    expected_boundaries: list[float],
) -> list[dict[str, Any]]:
    candidate_times = [candidate.boundary_seconds for candidate in result.candidates]
    summaries: list[dict[str, Any]] = []
    for expected in expected_boundaries:
        ranked = [
            (rank, abs(candidate - expected), candidate)
            for rank, candidate in enumerate(candidate_times, start=1)
        ]
        if not ranked:
            summaries.append(
                {
                    "expected_boundary_seconds": expected,
                    "nearest_candidate_seconds": None,
                    "absolute_error_seconds": None,
                    "candidate_rank": None,
                    "hit_within_1_second": False,
                    "hit_within_2_seconds": False,
                }
            )
            continue
        rank, error, candidate = min(ranked, key=lambda item: (item[1], item[0]))
        summaries.append(
            {
                "expected_boundary_seconds": expected,
                "nearest_candidate_seconds": candidate,
                "absolute_error_seconds": error,
                "candidate_rank": rank,
                "hit_within_1_second": error <= 1.0,
                "hit_within_2_seconds": error <= 2.0,
            }
        )
    return summaries


def probe_track(
    track_id: str,
    path: Path,
    *,
    expected_boundaries: list[float],
    window_seconds: float,
    min_separation_seconds: float,
    threshold_mad: float,
    max_candidates: int,
) -> dict[str, Any]:
    source_version_id = uuid5(NAMESPACE_URL, f"listencloser-change-probe:{track_id}:source")
    report_version_id = uuid5(NAMESPACE_URL, f"listencloser-change-probe:{track_id}:report")
    report = extract_perceptual_evidence_from_bytes(
        path.read_bytes(),
        source_version_id=source_version_id,
        fmt=_format(path),
    )
    result = discover_measured_change_candidates(
        report,
        evidence_report_version_id=report_version_id,
        window_seconds=window_seconds,
        min_separation_seconds=min_separation_seconds,
        threshold_mad=threshold_mad,
        max_candidates=max_candidates,
    )
    return {
        "track_id": track_id,
        "path": str(path),
        "duration_seconds": report.duration_seconds,
        "expected_boundaries": _expected_summary(result, expected_boundaries),
        "result": result.model_dump(mode="json"),
    }


def run_probe(
    tracks: list[tuple[str, Path]],
    *,
    expected_by_track: dict[str, list[float]],
    window_seconds: float,
    min_separation_seconds: float,
    threshold_mad: float,
    max_candidates: int,
) -> dict[str, Any]:
    return {
        "evidence_class": "REAL_AUDIO_MEASURED_CHANGE_DISCOVERY",
        "scope": "evaluation_only",
        "truth_boundary": (
            "candidate means measured descriptor change only; no section/drop/importance semantics"
        ),
        "method_policy": (
            "existing-stack transparent control first; ruptures remains optional only if a residual "
            "localization or method need is demonstrated"
        ),
        "versions": {
            "numpy": _package_version("numpy"),
            "scipy": _package_version("scipy"),
            "librosa": _package_version("librosa"),
        },
        "parameters": {
            "window_seconds": window_seconds,
            "min_separation_seconds": min_separation_seconds,
            "threshold_mad": threshold_mad,
            "max_candidates": max_candidates,
        },
        "tracks": [
            probe_track(
                track_id,
                path,
                expected_boundaries=expected_by_track.get(track_id, []),
                window_seconds=window_seconds,
                min_separation_seconds=min_separation_seconds,
                threshold_mad=threshold_mad,
                max_candidates=max_candidates,
            )
            for track_id, path in tracks
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--track",
        action="append",
        nargs=2,
        metavar=("ID", "PATH"),
        default=[],
        help="Track identifier and path; repeat for multiple tracks.",
    )
    parser.add_argument(
        "--expected-boundary",
        action="append",
        nargs=2,
        metavar=("ID", "SECONDS"),
        default=[],
        help="Known boundary for one track; repeat as needed.",
    )
    parser.add_argument("--window-seconds", type=float, default=4.0)
    parser.add_argument("--min-separation-seconds", type=float, default=4.0)
    parser.add_argument("--threshold-mad", type=float, default=3.0)
    parser.add_argument("--max-candidates", type=int, default=8)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    tracks = [(track_id, Path(path)) for track_id, path in args.track]
    if not tracks:
        parser.error("at least one --track is required")

    expected_by_track: dict[str, list[float]] = {}
    for track_id, raw_seconds in args.expected_boundary:
        expected_by_track.setdefault(track_id, []).append(float(raw_seconds))

    result = run_probe(
        tracks,
        expected_by_track=expected_by_track,
        window_seconds=args.window_seconds,
        min_separation_seconds=args.min_separation_seconds,
        threshold_mad=args.threshold_mad,
        max_candidates=args.max_candidates,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
