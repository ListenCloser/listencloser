"""Supplemental predeclared positive real-music probe for issue #812.

The candidate method is unchanged from issue_812_recurrence_probe. CENS chroma is
used only to localize an independently declared expected return; it is not a
candidate recurrence method or production proposal.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import librosa
import numpy as np

from domain.perceptual_report import DEFAULT_HOP_LENGTH
from perceptual_evidence import CANONICAL_SAMPLE_RATE, canonicalize_audio_bytes
from issue_812_recurrence_probe import (
    DEDUP_OVERLAP_FRACTION,
    RECURRENCE_DIMENSIONS,
    _fetch_exact_git_blob,
    _frame_matrix,
    _rank_recurrence,
    _span_overlap_fraction,
    _write_clip,
)

WORK = "Johannes Brahms — Hungarian Dance No. 5 / US Army Strings"
FILE_PATH = "audio/Hungarian_Dance_number_5_-_Allegro_in_F_sharp_minor_(string_orchestra).ogg"
GIT_BLOB_SHA = "c595edaf5bb2f79ccb5c45ae282bffcc27451c43"
SUBJECT = (1.0, 5.0)
CHROMA_EXPECTED_THRESHOLD = 0.85
MAX_ANCHORS = 5


def _framewise_cosine(query: np.ndarray, candidate: np.ndarray) -> float:
    if query.shape != candidate.shape or query.ndim != 2:
        raise ValueError("chroma windows must have equal 2D shape")
    dots = np.sum(query * candidate, axis=0)
    norms = np.linalg.norm(query, axis=0) * np.linalg.norm(candidate, axis=0)
    cosine = np.divide(dots, norms, out=np.zeros_like(dots), where=norms > 1e-12)
    return float(np.mean(cosine))


def _chroma_anchor(audio: np.ndarray) -> dict[str, object]:
    chroma = librosa.feature.chroma_cens(
        y=audio,
        sr=CANONICAL_SAMPLE_RATE,
        hop_length=DEFAULT_HOP_LENGTH,
    )
    frame_times = librosa.frames_to_time(
        np.arange(chroma.shape[1]),
        sr=CANONICAL_SAMPLE_RATE,
        hop_length=DEFAULT_HOP_LENGTH,
    )
    selected = np.flatnonzero(
        np.logical_and(frame_times >= SUBJECT[0], frame_times < SUBJECT[1])
    )
    if len(selected) < 4 or selected[-1] - selected[0] + 1 != len(selected):
        raise RuntimeError("Brahms subject did not map to sufficient contiguous chroma frames")
    subject_start = int(selected[0])
    subject_end = int(selected[-1] + 1)
    window_frames = subject_end - subject_start
    query = chroma[:, subject_start:subject_end]
    ranked: list[tuple[float, int]] = []

    for candidate_start in range(subject_end, chroma.shape[1] - window_frames + 1):
        candidate = chroma[:, candidate_start : candidate_start + window_frames]
        ranked.append((_framewise_cosine(query, candidate), candidate_start))
    ranked.sort(key=lambda item: (-item[0], item[1]))

    selected_anchors: list[tuple[float, int]] = []
    for similarity, candidate_start in ranked:
        if any(
            max(
                0,
                min(candidate_start + window_frames, prior_start + window_frames)
                - max(candidate_start, prior_start),
            )
            / window_frames
            >= DEDUP_OVERLAP_FRACTION
            for _, prior_start in selected_anchors
        ):
            continue
        selected_anchors.append((similarity, candidate_start))
        if len(selected_anchors) >= MAX_ANCHORS:
            break

    windows = []
    for rank, (similarity, start_frame) in enumerate(selected_anchors, start=1):
        start_seconds = float(frame_times[start_frame])
        windows.append(
            {
                "rank": rank,
                "start_seconds": start_seconds,
                "end_seconds": start_seconds + (SUBJECT[1] - SUBJECT[0]),
                "mean_framewise_cosine_similarity": similarity,
            }
        )
    return {
        "method": "librosa_chroma_cens_mean_framewise_cosine",
        "purpose": "independent_expected_occurrence_localization_only",
        "threshold": CHROMA_EXPECTED_THRESHOLD,
        "top_windows": windows,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("issue-812-probe-output"))
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)

    audio_bytes = _fetch_exact_git_blob(GIT_BLOB_SHA)
    audio = canonicalize_audio_bytes(audio_bytes, fmt="ogg")
    duration_seconds = len(audio) / CANONICAL_SAMPLE_RATE
    times, matrix = _frame_matrix(audio)

    anchor = _chroma_anchor(audio)
    top_anchor = anchor["top_windows"][0] if anchor["top_windows"] else None
    expected = (
        [top_anchor]
        if top_anchor is not None
        and top_anchor["mean_framewise_cosine_similarity"] >= CHROMA_EXPECTED_THRESHOLD
        else []
    )
    expected_state = "frozen_chroma_localized_return" if expected else "ambiguous"

    matches, coverage = _rank_recurrence(
        times,
        matrix,
        subject_start_seconds=SUBJECT[0],
        subject_end_seconds=SUBJECT[1],
        audio_duration_seconds=duration_seconds,
    )
    expected_rank = None
    if expected:
        for match in matches:
            if _span_overlap_fraction(match, expected[0]) >= DEDUP_OVERLAP_FRACTION:
                expected_rank = match["rank"]
                break

    clip_dir = args.output / "hungarian_dance_5"
    clip_dir.mkdir(parents=True, exist_ok=True)
    _write_clip(clip_dir / "subject.wav", audio, *SUBJECT)
    for match in matches:
        _write_clip(
            clip_dir / f"candidate_{match['rank']}.wav",
            audio,
            match["start_seconds"],
            match["end_seconds"],
        )
    if expected:
        _write_clip(
            clip_dir / "expected_chroma_anchor.wav",
            audio,
            expected[0]["start_seconds"],
            expected[0]["end_seconds"],
        )

    result = {
        "issue": 812,
        "work": WORK,
        "exact_source_version": {
            "kind": "external_git_blob",
            "repository": "librosa/data",
            "path": FILE_PATH,
            "git_blob_sha": GIT_BLOB_SHA,
            "verified_git_object_sha": True,
            "listencloser_version_row": None,
        },
        "license": "Public Domain / CC Public Domain Mark 1.0",
        "subject_span": list(SUBJECT),
        "recurrence_question": (
            "Does the selected opening string phrase/gesture have a distinct later return that is "
            "useful to hear side-by-side?"
        ),
        "expected_related_occurrences": expected,
        "expected_state": expected_state,
        "independent_chroma_check": anchor,
        "method": "numpy_equal_weight_length_normalized_z_euclidean_6d",
        "input_evidence_dimensions": list(RECURRENCE_DIMENSIONS),
        "candidate_spans": matches,
        "expected_occurrence_rank": expected_rank,
        "coverage_sufficiency": coverage,
        "window_policy": "fixed duration equal to subject frame count",
        "exclusion_overlap_policy": {
            "subject_overlap": "exclude all subject-overlapping candidate windows",
            "candidate_dedupe": "greedy; suppress candidate overlap >= 50% of subject window",
        },
        "audible_inspection_result": "pending_human_listen_to_emitted_clips",
        "useful": "ambiguous_pending_audible_inspection",
        "failure_mode": None,
        "audio_duration_seconds": duration_seconds,
        "clip_directory": str(clip_dir),
        "decision": "RESEARCH_REVISIT_PENDING_AUDIBLE_INSPECTION",
    }
    path = args.output / "results_hungarian.json"
    path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
