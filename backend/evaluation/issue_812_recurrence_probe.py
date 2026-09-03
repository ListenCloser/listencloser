"""One-off real-music activation probe for issue #812.

This is evaluation-only. It uses the production perceptual evidence extractor and
the transparent NumPy distance semantics learned in closed/unmerged PR #822.
It does not define a production recurrence API, threshold, confidence, section,
motif, or generic musical-similarity claim.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import math
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np
import soundfile as sf

from domain.perceptual_report import DEFAULT_HOP_LENGTH, DEFAULT_N_FFT, PREPROCESSING_VERSION
from perceptual_evidence import (
    CANONICAL_SAMPLE_RATE,
    canonicalize_audio_bytes,
    extract_measured_perceptual_series,
)

RECURRENCE_DIMENSIONS = (
    "onset_strength",
    "spectral_centroid",
    "band_low",
    "band_low_mid",
    "band_mid",
    "band_high",
)
CONSTANT_STD_THRESHOLD = 1e-8
PCM_EXPECTED_CORRELATION = 0.90
DEDUP_OVERLAP_FRACTION = 0.50
MAX_MATCHES = 5


@dataclass(frozen=True)
class SourceSpec:
    work: str
    file_path: str
    git_blob_sha: str
    license_note: str
    subject_start_seconds: float
    subject_end_seconds: float
    recurrence_question: str
    expected_policy: str


SOURCES = (
    SourceSpec(
        work='Admiral Bob feat. Snowflake — "Choice" (drum+bass excerpt)',
        file_path="audio/admiralbob77_-_Choice_-_Drum-bass.ogg",
        git_blob_sha="550fee9ca62bbfc027f4694c91bfce7b77257750",
        license_note=(
            "CC BY-NC; librosa/data metadata says this excerpt was truncated/modified "
            "to contain only the drum and bass tracks."
        ),
        subject_start_seconds=2.0,
        subject_end_seconds=6.0,
        recurrence_question="Find a distinct later return of the selected drum+bass groove/texture shape.",
        expected_policy=(
            "Freeze the best later equal-duration canonical-PCM window only if gain/offset-normalized "
            "waveform Pearson correlation is >= 0.90; otherwise expected occurrence is ambiguous."
        ),
    ),
    SourceSpec(
        work='Mihai Sorohan — "solo trumpet 06"',
        file_path="audio/sorohanro_-_solo-trumpet-06.ogg",
        git_blob_sha="fcdedb8caeeb3df6c6d3d6cb0ce1bfc340623096",
        license_note="CC BY; source metadata identifies a jazz trumpet loop-pack excerpt in F at 90 BPM.",
        subject_start_seconds=0.5,
        subject_end_seconds=2.5,
        recurrence_question=(
            "Negative query: no separate useful non-overlapping return should be surfaced; adjacent or "
            "same-timbre trumpet material is not success."
        ),
        expected_policy="Predeclared negative: expected related occurrences = none.",
    ),
)


def _fetch_exact_git_blob(blob_sha: str) -> bytes:
    url = f"https://api.github.com/repos/librosa/data/git/blobs/{blob_sha}"
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "listencloser-issue-812-evaluation",
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = json.load(response)
    if payload.get("sha") != blob_sha or payload.get("encoding") != "base64":
        raise RuntimeError(f"unexpected GitHub blob response for {blob_sha}")
    raw = base64.b64decode(payload["content"], validate=False)
    git_object = f"blob {len(raw)}\0".encode() + raw
    actual_sha = hashlib.sha1(git_object).hexdigest()  # noqa: S324 -- Git object identity uses SHA-1.
    if actual_sha != blob_sha:
        raise RuntimeError(f"blob identity mismatch: expected {blob_sha}, got {actual_sha}")
    return raw


def _frame_matrix(audio: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    measured = extract_measured_perceptual_series(
        audio,
        CANONICAL_SAMPLE_RATE,
        n_fft=DEFAULT_N_FFT,
        hop_length=DEFAULT_HOP_LENGTH,
    )
    onset = measured["onset_strength"]
    centroid = measured["spectral_centroid"]
    bands = measured["relative_band_energy"]
    times = np.asarray(onset.frame_times_seconds, dtype=float)
    centroid_times = np.asarray(centroid.frame_times_seconds, dtype=float)
    band_times = np.asarray(bands.frame_times_seconds, dtype=float)
    if not (
        len(times) == len(centroid_times) == len(band_times)
        and np.allclose(times, centroid_times, rtol=0.0, atol=1e-9)
        and np.allclose(times, band_times, rtol=0.0, atol=1e-9)
    ):
        raise RuntimeError("production perceptual dimensions did not share one exact frame grid")
    band_values = np.asarray(bands.values, dtype=float)
    if tuple(bands.parameters.get("band_order", ())) != ("low", "low_mid", "mid", "high"):
        raise RuntimeError("unexpected production coarse-band order")
    matrix = np.vstack(
        (
            np.asarray(onset.values, dtype=float),
            np.asarray(centroid.values, dtype=float),
            band_values[:, 0],
            band_values[:, 1],
            band_values[:, 2],
            band_values[:, 3],
        )
    )
    if matrix.shape != (6, len(times)) or not np.isfinite(matrix).all():
        raise RuntimeError(f"invalid perceptual matrix shape/values: {matrix.shape}")
    return times, matrix


def _subject_frame_range(times: np.ndarray, start: float, end: float) -> tuple[int, int]:
    selected = np.flatnonzero(np.logical_and(times >= start, times < end))
    if len(selected) < 4 or selected[-1] - selected[0] + 1 != len(selected):
        raise RuntimeError("subject span did not map to sufficient contiguous production evidence")
    return int(selected[0]), int(selected[-1] + 1)


def _normalized_component_distance(query: np.ndarray, candidate: np.ndarray) -> float:
    query_std = float(np.std(query))
    candidate_std = float(np.std(candidate))
    query_constant = query_std < CONSTANT_STD_THRESHOLD
    candidate_constant = candidate_std < CONSTANT_STD_THRESHOLD
    if query_constant and candidate_constant:
        return 0.0
    if query_constant != candidate_constant:
        return 1.0
    query_z = (query - float(np.mean(query))) / query_std
    candidate_z = (candidate - float(np.mean(candidate))) / candidate_std
    return float(np.linalg.norm(query_z - candidate_z) / math.sqrt(query.size))


def _overlap_frames(start_a: int, start_b: int, window_frames: int) -> int:
    return max(0, min(start_a + window_frames, start_b + window_frames) - max(start_a, start_b))


def _rank_recurrence(
    times: np.ndarray,
    matrix: np.ndarray,
    *,
    subject_start_seconds: float,
    subject_end_seconds: float,
    audio_duration_seconds: float,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    subject_start, subject_end = _subject_frame_range(
        times,
        subject_start_seconds,
        subject_end_seconds,
    )
    window_frames = subject_end - subject_start
    query = matrix[:, subject_start:subject_end]
    candidate_count = matrix.shape[1] - window_frames + 1
    ranked: list[tuple[float, int, list[float]]] = []
    subject_duration = subject_end_seconds - subject_start_seconds

    for candidate_start in range(candidate_count):
        candidate_end = candidate_start + window_frames
        if candidate_start < subject_end and candidate_end > subject_start:
            continue
        candidate_start_seconds = float(times[candidate_start])
        if candidate_start_seconds + subject_duration > audio_duration_seconds + 1e-9:
            continue
        candidate = matrix[:, candidate_start:candidate_end]
        components = [
            _normalized_component_distance(query[index], candidate[index]) for index in range(6)
        ]
        ranked.append((float(np.mean(components)), candidate_start, components))

    ranked.sort(key=lambda item: (item[0], item[1]))
    selected: list[tuple[float, int, list[float]]] = []
    for aggregate, candidate_start, components in ranked:
        if any(
            _overlap_frames(candidate_start, prior_start, window_frames) / window_frames
            >= DEDUP_OVERLAP_FRACTION
            for _, prior_start, _ in selected
        ):
            continue
        selected.append((aggregate, candidate_start, components))
        if len(selected) >= MAX_MATCHES:
            break

    matches: list[dict[str, Any]] = []
    for rank, (aggregate, candidate_start, components) in enumerate(selected, start=1):
        start_seconds = float(times[candidate_start])
        matches.append(
            {
                "rank": rank,
                "start_seconds": start_seconds,
                "end_seconds": start_seconds + subject_duration,
                "distance": aggregate,
                "component_distances": dict(zip(RECURRENCE_DIMENSIONS, components, strict=True)),
            }
        )

    coverage = {
        "frame_count": int(matrix.shape[1]),
        "subject_frame_count": int(window_frames),
        "candidate_window_count_before_exclusion": int(candidate_count),
        "eligible_window_count_after_subject_exclusion": int(len(ranked)),
        "sufficiency": "sufficient" if ranked and window_frames >= 4 else "insufficient",
    }
    return matches, coverage


def _pcm_window_correlation(query: np.ndarray, candidate: np.ndarray) -> float:
    query_centered = query - float(np.mean(query))
    candidate_centered = candidate - float(np.mean(candidate))
    denominator = float(np.linalg.norm(query_centered) * np.linalg.norm(candidate_centered))
    if denominator <= 1e-12:
        return 1.0 if np.allclose(query, candidate, rtol=0.0, atol=1e-8) else 0.0
    return float(np.dot(query_centered, candidate_centered) / denominator)


def _independent_pcm_anchor(
    audio: np.ndarray,
    *,
    subject_start_seconds: float,
    subject_end_seconds: float,
    later_only: bool,
) -> dict[str, Any]:
    start_sample = int(round(subject_start_seconds * CANONICAL_SAMPLE_RATE))
    end_sample = int(round(subject_end_seconds * CANONICAL_SAMPLE_RATE))
    query = audio[start_sample:end_sample]
    window_samples = len(query)
    first_start = end_sample if later_only else 0
    candidates: list[tuple[float, int]] = []
    for candidate_start in range(first_start, len(audio) - window_samples + 1, DEFAULT_HOP_LENGTH):
        candidate_end = candidate_start + window_samples
        if candidate_start < end_sample and candidate_end > start_sample:
            continue
        correlation = _pcm_window_correlation(query, audio[candidate_start:candidate_end])
        candidates.append((correlation, candidate_start))
    candidates.sort(key=lambda item: (-item[0], item[1]))
    deduped: list[tuple[float, int]] = []
    for correlation, candidate_start in candidates:
        if any(
            max(
                0,
                min(candidate_start + window_samples, prior_start + window_samples)
                - max(candidate_start, prior_start),
            )
            / window_samples
            >= DEDUP_OVERLAP_FRACTION
            for _, prior_start in deduped
        ):
            continue
        deduped.append((correlation, candidate_start))
        if len(deduped) >= MAX_MATCHES:
            break
    top = [
        {
            "rank": rank,
            "start_seconds": start / CANONICAL_SAMPLE_RATE,
            "end_seconds": (start + window_samples) / CANONICAL_SAMPLE_RATE,
            "pearson_correlation": correlation,
        }
        for rank, (correlation, start) in enumerate(deduped, start=1)
    ]
    return {
        "method": "canonical_pcm_gain_offset_normalized_pearson",
        "search_hop_samples": DEFAULT_HOP_LENGTH,
        "search_hop_seconds": DEFAULT_HOP_LENGTH / CANONICAL_SAMPLE_RATE,
        "threshold_for_literal_near_literal_anchor": PCM_EXPECTED_CORRELATION,
        "top_windows": top,
    }


def _span_overlap_fraction(a: dict[str, Any], b: dict[str, Any]) -> float:
    overlap = max(0.0, min(a["end_seconds"], b["end_seconds"]) - max(a["start_seconds"], b["start_seconds"]))
    duration = max(1e-12, b["end_seconds"] - b["start_seconds"])
    return overlap / duration


def _write_clip(path: Path, audio: np.ndarray, start: float, end: float) -> None:
    start_sample = max(0, int(round(start * CANONICAL_SAMPLE_RATE)))
    end_sample = min(len(audio), int(round(end * CANONICAL_SAMPLE_RATE)))
    sf.write(path, audio[start_sample:end_sample], CANONICAL_SAMPLE_RATE, subtype="PCM_16")


def _evaluate_source(spec: SourceSpec, output_dir: Path) -> dict[str, Any]:
    audio_bytes = _fetch_exact_git_blob(spec.git_blob_sha)
    audio = canonicalize_audio_bytes(audio_bytes, fmt="ogg")
    duration_seconds = len(audio) / CANONICAL_SAMPLE_RATE
    times, matrix = _frame_matrix(audio)

    pcm_anchor = _independent_pcm_anchor(
        audio,
        subject_start_seconds=spec.subject_start_seconds,
        subject_end_seconds=spec.subject_end_seconds,
        later_only=spec.git_blob_sha == SOURCES[0].git_blob_sha,
    )
    if spec.git_blob_sha == SOURCES[0].git_blob_sha:
        best_pcm = pcm_anchor["top_windows"][0] if pcm_anchor["top_windows"] else None
        expected_occurrences = (
            [best_pcm]
            if best_pcm is not None
            and best_pcm["pearson_correlation"] >= PCM_EXPECTED_CORRELATION
            else []
        )
        expected_state = "frozen_literal_or_near_literal" if expected_occurrences else "ambiguous"
    else:
        expected_occurrences = []
        expected_state = "predeclared_negative"

    matches, coverage = _rank_recurrence(
        times,
        matrix,
        subject_start_seconds=spec.subject_start_seconds,
        subject_end_seconds=spec.subject_end_seconds,
        audio_duration_seconds=duration_seconds,
    )

    expected_rank = None
    if expected_occurrences:
        expected = expected_occurrences[0]
        for match in matches:
            if _span_overlap_fraction(match, expected) >= DEDUP_OVERLAP_FRACTION:
                expected_rank = match["rank"]
                break

    slug = "choice_drumbass" if spec.git_blob_sha == SOURCES[0].git_blob_sha else "solo_trumpet_06"
    clip_dir = output_dir / slug
    clip_dir.mkdir(parents=True, exist_ok=True)
    _write_clip(
        clip_dir / "subject.wav",
        audio,
        spec.subject_start_seconds,
        spec.subject_end_seconds,
    )
    for match in matches:
        _write_clip(
            clip_dir / f"candidate_{match['rank']}.wav",
            audio,
            match["start_seconds"],
            match["end_seconds"],
        )
    if expected_occurrences:
        expected = expected_occurrences[0]
        _write_clip(
            clip_dir / "expected_pcm_anchor.wav",
            audio,
            expected["start_seconds"],
            expected["end_seconds"],
        )

    return {
        "work": spec.work,
        "exact_source_version": {
            "kind": "external_git_blob",
            "repository": "librosa/data",
            "path": spec.file_path,
            "git_blob_sha": spec.git_blob_sha,
            "verified_git_object_sha": True,
            "listencloser_version_row": None,
        },
        "license": spec.license_note,
        "subject_span": [spec.subject_start_seconds, spec.subject_end_seconds],
        "recurrence_question": spec.recurrence_question,
        "expected_policy": spec.expected_policy,
        "expected_related_occurrences": expected_occurrences,
        "expected_state": expected_state,
        "independent_pcm_check": pcm_anchor,
        "method": "numpy_equal_weight_length_normalized_z_euclidean_6d",
        "input_evidence_dimensions": list(RECURRENCE_DIMENSIONS),
        "preprocessing": {
            "production_preprocessing_version": PREPROCESSING_VERSION,
            "sample_rate_hz": CANONICAL_SAMPLE_RATE,
            "channel_mode": "mono",
            "n_fft": DEFAULT_N_FFT,
            "hop_length": DEFAULT_HOP_LENGTH,
            "rms_included": False,
        },
        "window_policy": "fixed duration equal to subject frame count",
        "exclusion_overlap_policy": {
            "subject_overlap": "exclude all subject-overlapping candidate windows",
            "candidate_dedupe": "greedy; suppress candidate overlap >= 50% of subject window",
        },
        "candidate_spans": matches,
        "expected_occurrence_rank": expected_rank,
        "coverage_sufficiency": coverage,
        "audible_inspection_result": "pending_human_listen_to_emitted_clips",
        "useful": "ambiguous_pending_audible_inspection",
        "failure_mode": None,
        "audio_duration_seconds": duration_seconds,
        "clip_directory": str(clip_dir),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("issue-812-probe-output"))
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)

    results = {
        "issue": 812,
        "decision_question": (
            "Does the transparent existing-stack recurrence relation surface candidates a musician "
            "would actually find useful?"
        ),
        "protocol": {
            "query_declaration": "frozen on issue #812 before scorer output",
            "distance_semantics_source": "closed/unmerged PR #822; reproduced here only for the run",
            "new_dependencies": [],
            "production_integration": False,
        },
        "records": [_evaluate_source(source, args.output) for source in SOURCES],
        "decision": "RESEARCH_REVISIT_PENDING_AUDIBLE_INSPECTION",
        "reopening_trigger": (
            "Listen to each emitted subject/candidate set and record whether expected returns are useful, "
            "false positives are annoying, and the loop adds value beyond scrubbing/navigation."
        ),
    }
    result_path = args.output / "results.json"
    result_path.write_text(json.dumps(results, indent=2, sort_keys=True) + "\n")
    print(json.dumps(results, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
