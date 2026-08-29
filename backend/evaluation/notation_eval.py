"""Notation quality evaluation harness.

Measures score quality in two explicit modes:

* ``reference_midi_to_score`` isolates notation/engraving quality by feeding
  aligned reference notes through the production audio-derived metric grid and
  notation path.
* ``audio_to_predicted_midi_to_score`` exercises the production Basic Pitch
  transcription seam first, then feeds that predicted MIDI through the same
  metric grid and notation path.

Keeping both modes on the same source-audio beat grid lets the report attribute
how much degradation is already present in note evidence versus how much is
introduced by notation. This module is evaluation-only; it does not change
production routing or score-generation behavior.

Usage:
    python -m evaluation.notation_eval \
      --manifest evaluation/corpora/real_world_v1.json \
      --mode both
"""

from __future__ import annotations

import argparse
import io
import json
import os
import tempfile
from dataclasses import asdict
from pathlib import Path
from typing import Any, Literal

import pretty_midi

from evaluation.analysis_v3.multitrack_transcription.metrics import NoteEvent, match_notes
from evaluation.models import CorpusManifest, EvalClip
from evaluation.notation_metrics import diagnose_musicxml

NotationEvalMode = Literal[
    "reference_midi_to_score",
    "audio_to_predicted_midi_to_score",
]
RunMode = NotationEvalMode | Literal["both"]


def evaluate_notation(
    generated_musicxml: bytes,
    reference_musicxml: bytes | None,
) -> dict[str, Any]:
    """Evaluate generated MusicXML against reference structural properties."""
    result: dict[str, Any] = {
        "structural": diagnose_musicxml(generated_musicxml).to_dict(),
        "accuracy": None,
    }

    if reference_musicxml:
        ref_diag = diagnose_musicxml(reference_musicxml).to_dict()
        result["reference_structural"] = ref_diag

        gen_notes = result["structural"]["total_note_count"]
        ref_notes = ref_diag["total_note_count"]
        result["note_count_ratio"] = gen_notes / ref_notes if ref_notes > 0 else None

        gen_measures = result["structural"]["measure_count"]
        ref_measures = ref_diag["measure_count"]
        result["measure_count_ratio"] = gen_measures / ref_measures if ref_measures > 0 else None

        gen_ties = result["structural"]["tie_count"]
        ref_ties = ref_diag["tie_count"]
        result["tie_ratio"] = gen_ties / ref_ties if ref_ties > 0 else None

    return result


def _load_note_events(midi_bytes: bytes) -> list[NoteEvent]:
    """Normalize non-drum MIDI notes to the shared Analysis V3 AMT contract."""
    midi = pretty_midi.PrettyMIDI(io.BytesIO(midi_bytes))
    events: list[NoteEvent] = []
    for instrument in midi.instruments:
        if instrument.is_drum:
            continue
        for note in instrument.notes:
            if note.end <= note.start:
                continue
            events.append(
                NoteEvent(
                    pitch=int(note.pitch),
                    start=float(note.start),
                    end=float(note.end),
                    program=int(instrument.program),
                    is_drum=False,
                )
            )
    return events


def _score_transcription(reference_midi: bytes, predicted_midi: bytes) -> dict[str, Any]:
    """Score predicted notes with the existing canonical Analysis V3 metrics."""
    reference = _load_note_events(reference_midi)
    predicted = _load_note_events(predicted_midi)
    return {
        "onset_flat": asdict(match_notes(reference, predicted)),
        "note_flat": asdict(match_notes(reference, predicted, require_offset=True)),
    }


def _run_product_transcription(audio_path: Path, output_midi: Path) -> dict[str, Any]:
    """Exercise the same BasicPitchEngine adapter used by Analysis V3 evaluation."""
    from evaluation.analysis_v3.multitrack_transcription.adapters.basic_pitch import (
        run_basic_pitch,
    )

    return run_basic_pitch(audio_path, output_midi)


def _production_audio_grid(audio_path: Path) -> tuple[float, list[float]]:
    """Decode upload audio and run the production librosa beat-grid estimator."""
    from music_features import decode_audio_to_wav, estimate_beat_grid

    raw = audio_path.read_bytes()
    fmt = audio_path.suffix.lstrip(".") or "wav"
    decoded_wav = decode_audio_to_wav(raw, fmt=fmt)
    return estimate_beat_grid(decoded_wav)


def _notation_from_midi(
    midi_bytes: bytes,
    beat_times: list[float],
) -> tuple[bytes, dict[str, Any]]:
    """Run the current production notation reduction/engine without modification."""
    from music_features import notation_midi_from_performance, notation_with_engine

    notation_midi, quantization = notation_midi_from_performance(midi_bytes, beat_times)
    result = notation_with_engine(notation_midi, beat_times)
    return result.get("musicxml", b""), dict(quantization)


def evaluate_clip(clip: EvalClip, mode: NotationEvalMode) -> dict[str, Any]:
    """Evaluate one clip while preserving explicit pipeline-stage attribution."""
    if not clip.reference_midi or not os.path.isfile(clip.reference_midi):
        raise ValueError("reference MIDI is required")
    if not clip.reference_musicxml or not os.path.isfile(clip.reference_musicxml):
        raise ValueError("reference MusicXML is required")
    if not os.path.isfile(clip.audio):
        raise ValueError("source audio is required")

    audio_path = Path(clip.audio)
    reference_midi = Path(clip.reference_midi).read_bytes()
    reference_musicxml = Path(clip.reference_musicxml).read_bytes()
    tempo_bpm, beat_times = _production_audio_grid(audio_path)

    transcription_stage: dict[str, Any]
    if mode == "reference_midi_to_score":
        notation_input = reference_midi
        transcription_stage = {
            "status": "not_run",
            "reason": "reference_midi_notation_ceiling",
        }
    elif mode == "audio_to_predicted_midi_to_score":
        with tempfile.TemporaryDirectory(prefix="hello-ai-notation-eval-") as temp_dir:
            predicted_path = Path(temp_dir) / "prediction.mid"
            measurement = _run_product_transcription(audio_path, predicted_path)
            predicted_midi = predicted_path.read_bytes()
        notation_input = predicted_midi
        accuracy = _score_transcription(reference_midi, predicted_midi)
        transcription_stage = {
            "status": "measured",
            "accuracy": accuracy,
            "runtime_seconds": measurement.get("runtime_seconds"),
            "process_max_rss_mb": measurement.get("process_max_rss_mb"),
            "predicted_notes_reported": measurement.get("predicted_notes"),
            "provenance": measurement.get("provenance", {}),
        }
    else:  # pragma: no cover - Literal callers and argparse choices constrain this.
        raise ValueError(f"unsupported notation evaluation mode: {mode}")

    generated_musicxml, quantization = _notation_from_midi(notation_input, beat_times)
    if not generated_musicxml:
        raise ValueError("notation engine returned no MusicXML")

    result = evaluate_notation(generated_musicxml, reference_musicxml)
    if mode == "audio_to_predicted_midi_to_score":
        result["accuracy"] = transcription_stage["accuracy"]

    result.update(
        {
            "clip_id": clip.id,
            "source_id": clip.source_id,
            "mode": mode,
            "stages": {
                "transcription": transcription_stage,
                "metric_grid": {
                    "source": "production_audio_librosa",
                    "tempo_bpm": round(float(tempo_bpm), 4),
                    "beat_count": len(beat_times),
                },
                "notation": {
                    "quantization": quantization,
                    "structural": result["structural"],
                    "reference_structural": result.get("reference_structural"),
                },
            },
        }
    )
    return result


def _modes_for_run(mode: RunMode) -> tuple[NotationEvalMode, ...]:
    if mode == "both":
        return ("reference_midi_to_score", "audio_to_predicted_midi_to_score")
    return (mode,)


def run_notation_evaluation(
    manifest_path: str,
    output_dir: str,
    *,
    mode: RunMode = "reference_midi_to_score",
) -> dict[str, Any]:
    """Run stage-attributed notation evaluation on all eligible manifest clips."""
    manifest = CorpusManifest.from_file(manifest_path)
    results: list[dict[str, Any]] = []

    for clip in manifest.clips:
        if not clip.reference_musicxml or not clip.reference_midi:
            continue

        for evaluation_mode in _modes_for_run(mode):
            print(f"Evaluating {clip.id} [{evaluation_mode}]...")
            try:
                eval_result = evaluate_clip(clip, evaluation_mode)
                results.append(eval_result)
                gen_notes = eval_result["structural"]["total_note_count"]
                ref_notes = eval_result.get("reference_structural", {}).get(
                    "total_note_count", "?"
                )
                gen_meas = eval_result["structural"]["measure_count"]
                ref_meas = eval_result.get("reference_structural", {}).get("measure_count", "?")
                gen_ties = eval_result["structural"]["tie_count"]
                ref_ties = eval_result.get("reference_structural", {}).get("tie_count", "?")
                print(f"  Notes: {gen_notes} (ref: {ref_notes})")
                print(f"  Measures: {gen_meas} (ref: {ref_meas})")
                print(f"  Ties: {gen_ties} (ref: {ref_ties})")
                accuracy = eval_result.get("accuracy")
                if accuracy:
                    print(f"  Transcription onset F1: {accuracy['onset_flat']['f1']:.4f}")
            except Exception as error:
                print(f"  Error: {error}")
                results.append(
                    {
                        "clip_id": clip.id,
                        "source_id": clip.source_id,
                        "mode": evaluation_mode,
                        "error": str(error),
                    }
                )

    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, "notation_eval.json")
    payload = {"mode": mode, "clips": results}
    with open(output_path, "w") as file_handle:
        json.dump(payload, file_handle, indent=2)
    print(f"\nResults saved to {output_path}")

    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate notation quality")
    parser.add_argument("--manifest", required=True, help="Path to corpus manifest")
    parser.add_argument(
        "--output-dir", default="evaluation/results/notation", help="Output directory"
    )
    parser.add_argument(
        "--mode",
        choices=(
            "reference_midi_to_score",
            "audio_to_predicted_midi_to_score",
            "both",
        ),
        default="reference_midi_to_score",
        help="Evaluation path to run; 'both' emits the notation ceiling and product path",
    )
    args = parser.parse_args()

    run_notation_evaluation(args.manifest, args.output_dir, mode=args.mode)


if __name__ == "__main__":
    main()
