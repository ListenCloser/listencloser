"""Compare an explicit transcription challenger against a named baseline.

This evaluator reuses the rights-safe real-audio corpus, slicing, reference
notes, and metrics from ``evaluation.real_audio`` while deliberately bypassing
profile routing.  It is for engine bakeoffs, not evidence about the production
``auto`` route.

Example (run in a worker runtime with both engines provisioned):

  python -m evaluation.transcription_engine \
    --candidate tsumugi --baseline basic_pitch --corpus real_audio_v1 \
    --output /tmp/tsumugi-vs-basic-pitch.json
"""

from __future__ import annotations

import argparse
import json
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from engines.base import TranscriptionEngine
from engines.registry import get_transcription_engine
from evaluation.datasets import cache
from evaluation.datasets.registry import resolve_clip
from evaluation.real_audio import (
    _category_summary,
    _load_clips,
    _reference_notes,
    _slice_audio,
)
from evaluation.transcription_metrics import Note, compute_note_metrics


def _transcribe_engine(
    wav_bytes: bytes,
    engine_name: str,
    *,
    engine_factory: Callable[..., TranscriptionEngine] = get_transcription_engine,
) -> tuple[list[Note], dict[str, Any]]:
    result = engine_factory(name=engine_name).transcribe(wav_bytes, fmt="wav")
    return [Note.from_dict(note) for note in result.notes], result.provenance.to_dict()


def run_engine(
    corpus: str,
    engine_name: str,
    *,
    engine_factory: Callable[..., TranscriptionEngine] = get_transcription_engine,
) -> list[dict[str, Any]]:
    prepared = cache.cache_dir()
    clips = _load_clips(corpus)
    results: list[dict[str, Any]] = []
    for clip in clips:
        try:
            resolved = resolve_clip(clip)
            audio_path = Path(resolved.audio_path)
            start = float(clip.get("excerpt_start", 0.0))
            end = float(clip.get("excerpt_end", 30.0))
            wav_bytes = _slice_audio(audio_path, start, end)
            reference = _reference_notes(clip, prepared)

            t0 = time.monotonic()
            predicted, provenance = _transcribe_engine(
                wav_bytes,
                engine_name,
                engine_factory=engine_factory,
            )
            elapsed = time.monotonic() - t0
            metrics = compute_note_metrics(predicted, reference) if reference else None
            results.append(
                {
                    "id": clip["id"],
                    "status": "ok",
                    "category": clip["category"],
                    "requested_engine": engine_name,
                    "effective_engine": provenance["engine"],
                    "provenance": provenance,
                    "predicted_notes": len(predicted),
                    "reference_notes": len(reference),
                    "time_s": round(elapsed, 2),
                    "metrics": metrics.to_dict() if metrics else None,
                }
            )
        except Exception as exc:
            results.append(
                {
                    "id": clip["id"],
                    "status": "error",
                    "category": clip["category"],
                    "requested_engine": engine_name,
                    "message": str(exc),
                }
            )
    return results


def _summary_delta(
    baseline: dict[str, dict[str, Any]],
    candidate: dict[str, dict[str, Any]],
) -> dict[str, dict[str, float]]:
    deltas: dict[str, dict[str, float]] = {}
    for category in sorted(set(baseline) & set(candidate)):
        base = baseline[category]
        challenger = candidate[category]
        deltas[category] = {
            "note_f1": round(challenger["note_f1"] - base["note_f1"], 4),
            "onset_f1": round(challenger["onset_f1"] - base["onset_f1"], 4),
            "excessive_rate": round(
                challenger["excessive_rate"] - base["excessive_rate"], 4
            ),
            "missed_rate": round(challenger["missed_rate"] - base["missed_rate"], 4),
            "avg_runtime_s": round(
                challenger["avg_runtime_s"] - base["avg_runtime_s"], 2
            ),
        }
    return deltas


def comparison_payload(
    corpus: str,
    baseline_engine: str,
    candidate_engine: str,
    baseline_rows: list[dict[str, Any]],
    candidate_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    baseline_summary = _category_summary(baseline_rows)
    candidate_summary = _category_summary(candidate_rows)
    return {
        "evaluation_id": "explicit_transcription_engine_bakeoff_v1",
        "corpus": corpus,
        "baseline_engine": baseline_engine,
        "candidate_engine": candidate_engine,
        "baseline_summary": baseline_summary,
        "candidate_summary": candidate_summary,
        "delta_candidate_minus_baseline": _summary_delta(
            baseline_summary,
            candidate_summary,
        ),
        "baseline_rows": baseline_rows,
        "candidate_rows": candidate_rows,
        "notes": [
            "This bypasses profile routing and compares explicitly named engines.",
            "Use evaluation.real_audio for evidence about the production auto profile.",
            "Errors remain explicit and are never converted into fallback-engine results.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare explicit transcription engines")
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--baseline", default="basic_pitch")
    parser.add_argument("--corpus", default="real_audio_v1")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    baseline_rows = run_engine(args.corpus, args.baseline)
    candidate_rows = run_engine(args.corpus, args.candidate)
    payload = comparison_payload(
        args.corpus,
        args.baseline,
        args.candidate,
        baseline_rows,
        candidate_rows,
    )

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(payload, indent=2) + "\n")
        print(args.output)
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
