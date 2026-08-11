"""CLI runner for the music evaluation framework.

Usage:
  python -m evaluation.runner --manifest path/to/manifest.json
  python -m evaluation.runner --manifest path/to/manifest.json --output results/
"""

from __future__ import annotations

import argparse
import json
import os
import tempfile
import time
from pathlib import Path
from typing import Any

from . import analysis_metrics, beat_metrics, notation_metrics, transcription_metrics
from .corpus import load_manifest, validate_clip_fixtures
from .models import EvalClip
from .report import write_markdown_report


def _run_clip(clip: EvalClip, output_dir: str) -> dict[str, Any]:
    """Run the full production pipeline on one clip and compute metrics."""
    import sys

    # Add backend to path so we can import production modules
    backend_dir = str(Path(__file__).resolve().parent.parent)
    if backend_dir not in sys.path:
        sys.path.insert(0, backend_dir)

    from analyze import analyze_midi
    from music_features import (
        convert_format,
        estimate_beat_grid,
        midi_to_wav,
        notation_midi_from_performance,
        transcribe_audio,
    )

    result: dict[str, Any] = {"clip_id": clip.id, "category": clip.category}

    audio_bytes = Path(clip.audio).read_bytes()

    t0 = time.monotonic()
    transcription = transcribe_audio(audio_bytes, fmt="wav")
    result["transcription_time_s"] = round(time.monotonic() - t0, 2)

    midi_bytes = transcription["midi"]
    notes = transcription.get("notes", [])
    num_notes = transcription["num_notes"]
    cleanup_report = transcription.get("cleanup_report", {})
    result["transcription_num_notes"] = num_notes
    result["transcription_cleanup"] = cleanup_report

    # --- Transcription metrics ---
    if clip.reference_midi:
        ref_midi = Path(clip.reference_midi).read_bytes()
        ref_notes = _midi_to_notes(ref_midi)
        pred_notes = [transcription_metrics.Note.from_dict(n) for n in notes]
        ref_note_objs = [transcription_metrics.Note.from_dict(n) for n in ref_notes]
        result["transcription_metrics"] = transcription_metrics.compute_note_metrics(
            pred_notes, ref_note_objs
        ).to_dict()

    # --- Render transcription audio ---
    try:
        t0 = time.monotonic()
        wav_bytes = midi_to_wav(midi_bytes)
        result["render_time_s"] = round(time.monotonic() - t0, 2)
        result["rendered_wav_size_bytes"] = len(wav_bytes)
    except Exception:
        wav_bytes = None
        result["render_time_s"] = None

    # --- Beat estimation ---
    t0 = time.monotonic()
    bpm_est, beat_times = estimate_beat_grid(audio_bytes)
    result["beat_time_s"] = round(time.monotonic() - t0, 2)
    result["estimated_bpm"] = round(bpm_est, 2)
    result["estimated_beats"] = len(beat_times)

    # --- Beat metrics ---
    ref_beats = clip.reference.beats if clip.reference.beats else None
    ref_bpm = clip.reference.bpm
    if ref_beats or ref_bpm is not None:
        result["beat_metrics"] = beat_metrics.compute_beat_metrics(
            predicted_beats=beat_times,
            predicted_bpm=float(bpm_est),
            predicted_downbeats=None,
            reference_beats=ref_beats,
            reference_bpm=ref_bpm,
            reference_downbeats=clip.reference.downbeats if clip.reference.downbeats else None,
        ).to_dict()

    # --- Notation ---
    try:
        notation_midi_bytes, quant_report = notation_midi_from_performance(midi_bytes, beat_times)
        musicxml_bytes = convert_format(notation_midi_bytes, "midi", "musicxml")
        result["notation_metrics"] = notation_metrics.diagnose_musicxml(musicxml_bytes).to_dict()
        result["notation_quantization"] = quant_report
    except Exception:
        result["notation_metrics"] = None
        result["notation_quantization"] = None

    # --- Analysis ---
    tmp_path: str | None = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".mid", delete=False) as tmp:
            tmp.write(midi_bytes)
            tmp.flush()
            tmp_path = tmp.name
        analysis = analyze_midi(tmp_path)
        result["analysis_key"] = f"{analysis['key']['tonic']} {analysis['key']['mode']}"
        result["analysis_tempo"] = round(float(analysis["tempo"]["bpm"]), 1)
        result["analysis_meter"] = (
            f"{analysis['time_signature']['numerator']}/{analysis['time_signature']['denominator']}"
        )
        result["analysis_sections"] = [
            {
                "start": s["position"],
                "end": s["position"],
                "label": s.get("type", s.get("kind", "")),
            }
            for s in analysis.get("cadences", [])
        ]
        chords_out = [
            {"root": c["root"], "quality": c["quality"], "start": c["start"], "end": c["end"]}
            for c in analysis.get("chords", [])
        ]
        result["analysis_chords_count"] = len(chords_out)

        result["analysis_metrics"] = analysis_metrics.compute_analysis_metrics(
            predicted_key=result["analysis_key"],
            predicted_bpm=float(analysis["tempo"]["bpm"]),
            predicted_meter=result["analysis_meter"],
            predicted_sections=result["analysis_sections"],
            predicted_chords=chords_out,
            reference=clip.reference,
        ).to_dict()
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)

    return result


def run_evaluation(manifest_path: str, output_dir: str = "evaluation/results") -> dict[str, Any]:
    os.makedirs(output_dir, exist_ok=True)

    manifest = load_manifest(manifest_path)

    # Validate fixtures
    issues: dict[str, list[str]] = {}
    for clip in manifest.clips:
        clip_issues = validate_clip_fixtures(clip)
        if clip_issues:
            issues[clip.id] = clip_issues
    if issues:
        print(f"Warning: fixture issues found: {json.dumps(issues, indent=2)}")

    results: list[dict[str, Any]] = []
    for i, clip in enumerate(manifest.clips):
        print(f"[{i + 1}/{len(manifest.clips)}] Evaluating {clip.id} ({clip.category})")
        try:
            r = _run_clip(clip, output_dir)
            results.append(r)
        except Exception as exc:
            results.append({"clip_id": clip.id, "error": str(exc)})
            print(f"  FAILED: {exc}")

    summary: dict[str, Any] = {
        "manifest": manifest_path,
        "name": manifest.name,
        "description": manifest.description,
        "clip_count": len(manifest.clips),
        "completed": len([r for r in results if "error" not in r]),
        "failed": len([r for r in results if "error" in r]),
        "results": results,
    }

    json_path = os.path.join(output_dir, "latest.json")
    with open(json_path, "w") as fh:
        json.dump(summary, fh, indent=2, default=str)

    md_path = os.path.join(output_dir, "latest.md")
    write_markdown_report(summary, md_path)

    print(f"\nDone. JSON: {json_path}  Markdown: {md_path}")
    return summary


def _midi_to_notes(midi_bytes: bytes) -> list[dict[str, Any]]:
    """Extract note list from MIDI bytes using music21 (available in backend deps)."""
    import io

    from music21 import converter

    s = converter.parse(io.BytesIO(midi_bytes))
    notes: list[dict[str, Any]] = []
    for n in s.flatten().notesAndRests:
        if hasattr(n, "pitch") and n.duration is not None:
            notes.append(
                {
                    "pitch": n.pitch.midi,
                    "start": float(n.offset),
                    "end": float(n.offset + float(n.duration.quarterLength) * 0.5),
                    "velocity": int(
                        getattr(n, "volume", None) and getattr(n.volume, "velocity", 64) or 64
                    ),
                }
            )
    return notes


def main() -> None:
    parser = argparse.ArgumentParser(description="Run music quality evaluation")
    parser.add_argument("--manifest", required=True, help="Path to corpus manifest JSON")
    parser.add_argument("--output", default="evaluation/results", help="Output directory")
    args = parser.parse_args()
    run_evaluation(args.manifest, args.output)


if __name__ == "__main__":
    main()
