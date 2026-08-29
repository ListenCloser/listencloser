"""Production-faithful piano transcription profile comparison.

This evaluator answers a narrow question without changing product routing:

    How do the exact production ``auto`` and ``solo_piano`` transcription
    profiles compare on the same materialized audio/reference-MIDI rows?

Unlike the generic OSS bakeoff adapters, this module delegates to
``engines.registry.get_transcription_engine`` and records the normalized
``TranscriptionResult`` returned by the production engine seam. Model inference
is opt-in; unit tests inject lightweight fake engines.

Usage:
    python -m evaluation.piano_transcription_profiles \
      --manifest evaluation/corpora/prepared-real-world.json \
      --hello-ai-sha <commit> \
      --output evaluation/results/piano_transcription_profiles.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import time
from collections.abc import Callable, Sequence
from functools import lru_cache
from pathlib import Path
from typing import Any

from engines.base import TranscriptionEngine
from engines.registry import get_transcription_engine
from evaluation.corpus import load_manifest
from evaluation.models import EvalClip
from evaluation.transcription_metrics import Note, compute_note_metrics, match_notes

Profile = str
EngineFactory = Callable[..., TranscriptionEngine]
CheckpointResolver = Callable[[dict[str, Any]], dict[str, Any]]


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _midi_to_notes(midi_bytes: bytes) -> list[Note]:
    import io

    import pretty_midi

    midi = pretty_midi.PrettyMIDI(io.BytesIO(midi_bytes))
    return [
        Note(pitch=note.pitch, start=note.start, end=note.end, velocity=note.velocity)
        for instrument in midi.instruments
        if not instrument.is_drum
        for note in instrument.notes
    ]


def _percentile(values: Sequence[float], quantile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(float(value) for value in values)
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * quantile
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def _rounded(value: float | None) -> float | None:
    return round(value, 4) if value is not None else None


def _duration_summary(notes: Sequence[Note]) -> dict[str, Any]:
    durations = [max(0.0, note.end - note.start) for note in notes]
    return {
        "count": len(durations),
        "median_seconds": _rounded(_percentile(durations, 0.5)),
        "p95_seconds": _rounded(_percentile(durations, 0.95)),
        "max_seconds": _rounded(max(durations) if durations else None),
    }


def _duration_error_summary(
    predicted: Sequence[Note],
    reference: Sequence[Note],
) -> dict[str, Any]:
    onset_matched, _, _ = match_notes(predicted, reference)
    signed_errors = [
        (pred.end - pred.start) - (ref.end - ref.start) for pred, ref in onset_matched
    ]
    absolute_errors = [abs(value) for value in signed_errors]
    return {
        "onset_matched_pairs": len(onset_matched),
        "median_signed_seconds": _rounded(_percentile(signed_errors, 0.5)),
        "median_absolute_seconds": _rounded(_percentile(absolute_errors, 0.5)),
        "p95_absolute_seconds": _rounded(_percentile(absolute_errors, 0.95)),
    }


@lru_cache(maxsize=1)
def _transkun_checkpoint_sha256() -> tuple[str | None, str | None]:
    """Hash the exact packaged checkpoint used by the production Transkun adapter."""
    try:
        import pkg_resources

        path = Path(
            pkg_resources.resource_filename(
                "transkun.transcribe",
                "pretrained/2.0.pt",
            )
        )
        if not path.is_file():
            return None, f"packaged checkpoint not found: {path}"
        return _sha256_file(path), None
    except Exception as error:
        return None, f"checkpoint fingerprint unavailable: {error}"


def _checkpoint_identity(provenance: dict[str, Any]) -> dict[str, Any]:
    engine = provenance.get("engine")
    if engine == "transkun":
        sha256, reason = _transkun_checkpoint_sha256()
        return {
            "model": provenance.get("model"),
            "sha256": sha256,
            "reason": reason,
        }
    return {
        "model": provenance.get("model"),
        "sha256": None,
        "reason": "production adapter does not expose a stable checkpoint path",
    }


def _clip_provenance(clip: EvalClip) -> dict[str, Any]:
    return {
        "dataset": clip.dataset,
        "split": clip.split,
        "source_id": clip.source_id,
        "license": clip.license,
        "category": clip.category,
        "excerpt_start": clip.excerpt_start,
        "excerpt_end": clip.excerpt_end,
    }


def _reference_notes(clip: EvalClip) -> tuple[list[Note] | None, dict[str, Any]]:
    if not clip.reference_midi:
        return None, {"status": "not_provided", "path": None}
    path = Path(clip.reference_midi)
    if not path.is_file():
        return None, {"status": "missing_file", "path": str(path)}
    return _midi_to_notes(path.read_bytes()), {
        "status": "available",
        "path": str(path),
        "sha256": _sha256_file(path),
    }


def evaluate_profile(
    clip: EvalClip,
    profile: Profile,
    *,
    engine_factory: EngineFactory = get_transcription_engine,
    checkpoint_resolver: CheckpointResolver = _checkpoint_identity,
) -> dict[str, Any]:
    """Run one clip through one exact production transcription profile."""
    row: dict[str, Any] = {
        "clip_id": clip.id,
        "requested_profile": profile,
        "effective_engine": None,
        "status": "failed",
        "clip_provenance": _clip_provenance(clip),
    }
    audio_path = Path(clip.audio)
    if not audio_path.is_file():
        row["error"] = f"source audio missing: {audio_path}"
        return row

    reference, reference_meta = _reference_notes(clip)
    row["reference_midi"] = reference_meta

    try:
        engine = engine_factory(profile=profile)
        started = time.monotonic()
        result = engine.transcribe(
            audio_path.read_bytes(),
            fmt=audio_path.suffix.lstrip(".").lower() or "wav",
        )
        runtime_seconds = time.monotonic() - started
    except Exception as error:
        row["error"] = str(error)
        return row

    provenance = result.provenance.to_dict()
    predicted = [Note.from_dict(note) for note in result.notes]
    row.update(
        {
            "effective_engine": provenance.get("engine"),
            "runtime_seconds": round(runtime_seconds, 4),
            "provenance": provenance,
            "checkpoint": checkpoint_resolver(provenance),
            "cleanup_report": result.cleanup_report,
            "predicted_note_count": len(predicted),
            "predicted_duration": _duration_summary(predicted),
            "tempo_is_placeholder": result.tempo_is_placeholder,
            "meter_is_placeholder": result.meter_is_placeholder,
            "supports_meter": result.supports_meter,
        }
    )

    if reference is None:
        row.update(
            {
                "status": "ineligible",
                "reason": "reference MIDI is required for transcription scoring",
                "reference_note_count": None,
                "note_count_ratio": None,
                "reference_duration": None,
                "duration_error": None,
                "metrics": None,
            }
        )
        return row

    metrics = compute_note_metrics(predicted, reference).to_dict()
    row.update(
        {
            "status": "measured",
            "reference_note_count": len(reference),
            "note_count_ratio": (
                round(len(predicted) / len(reference), 4) if reference else None
            ),
            "reference_duration": _duration_summary(reference),
            "duration_error": _duration_error_summary(predicted, reference),
            "metrics": metrics,
        }
    )
    return row


def _macro(rows: Sequence[dict[str, Any]], key: str) -> float | None:
    values = [
        float(row["metrics"][key])
        for row in rows
        if row.get("status") == "measured"
        and isinstance(row.get("metrics"), dict)
        and row["metrics"].get(key) is not None
    ]
    return round(sum(values) / len(values), 4) if values else None


def _aggregate(rows: Sequence[dict[str, Any]], profiles: Sequence[Profile]) -> dict[str, Any]:
    summary: dict[str, Any] = {}
    for profile in profiles:
        profile_rows = [row for row in rows if row["requested_profile"] == profile]
        measured = [row for row in profile_rows if row["status"] == "measured"]
        note_count_ratios = [
            float(row["note_count_ratio"])
            for row in measured
            if row.get("note_count_ratio") is not None
        ]
        summary[profile] = {
            "rows": len(profile_rows),
            "measured": len(measured),
            "ineligible": sum(row["status"] == "ineligible" for row in profile_rows),
            "failed": sum(row["status"] == "failed" for row in profile_rows),
            "macro_onset_precision": _macro(profile_rows, "onset_precision"),
            "macro_onset_recall": _macro(profile_rows, "onset_recall"),
            "macro_onset_f1": _macro(profile_rows, "onset_f1"),
            "macro_note_precision": _macro(profile_rows, "note_precision"),
            "macro_note_recall": _macro(profile_rows, "note_recall"),
            "macro_note_f1": _macro(profile_rows, "note_f1"),
            "mean_note_count_ratio": (
                round(sum(note_count_ratios) / len(note_count_ratios), 4)
                if note_count_ratios
                else None
            ),
        }
    return summary


def run_profile_comparison(
    manifest_path: str,
    *,
    profiles: Sequence[Profile] = ("auto", "solo_piano"),
    hello_ai_sha: str,
    limit: int | None = None,
    engine_factory: EngineFactory = get_transcription_engine,
    checkpoint_resolver: CheckpointResolver = _checkpoint_identity,
) -> dict[str, Any]:
    """Run every requested production profile on the same manifest rows."""
    manifest = load_manifest(manifest_path)
    clips = manifest.clips[:limit] if limit is not None else manifest.clips
    rows = [
        evaluate_profile(
            clip,
            profile,
            engine_factory=engine_factory,
            checkpoint_resolver=checkpoint_resolver,
        )
        for clip in clips
        for profile in profiles
    ]
    return {
        "evaluation_id": "piano_transcription_production_profiles_v1",
        "hello_ai_sha": hello_ai_sha,
        "manifest": {
            "name": manifest.name,
            "path": manifest_path,
            "sha256": _sha256_file(Path(manifest_path)),
            "clips": len(clips),
        },
        "profiles": list(profiles),
        "rows": rows,
        "summary": _aggregate(rows, profiles),
        "notes": [
            "Profiles invoke the production transcription engine registry directly.",
            "No production routing or cleanup behavior is changed by this evaluator.",
            "Rows without reference MIDI are retained as ineligible rather than dropped.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compare exact production piano transcription profiles"
    )
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--hello-ai-sha", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument(
        "--profiles",
        nargs="+",
        choices=("auto", "solo_piano"),
        default=("auto", "solo_piano"),
    )
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    payload = run_profile_comparison(
        args.manifest,
        profiles=args.profiles,
        hello_ai_sha=args.hello_ai_sha,
        limit=args.limit,
    )
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2) + "\n")
    print(output_path)


if __name__ == "__main__":
    main()
