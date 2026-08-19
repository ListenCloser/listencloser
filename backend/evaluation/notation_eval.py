"""Notation quality evaluation harness.

Evaluates transcription → notation pipeline against reference MusicXML scores.
Designed to work with ASAP dataset but extensible to other corpora.

Usage:
    python -m evaluation.notation_eval --manifest evaluation/corpora/real_world_v1.json
"""

from __future__ import annotations

import argparse
import json
import os
from typing import Any

import pretty_midi

from evaluation.models import CorpusManifest
from evaluation.notation_metrics import diagnose_musicxml


def evaluate_notation(
    generated_musicxml: bytes,
    reference_musicxml: bytes | None,
    reference_midi: bytes | None,
) -> dict[str, Any]:
    """Evaluate generated MusicXML against reference.

    Returns dict with structural diagnostics and accuracy metrics
    (when reference is available).
    """
    result: dict[str, Any] = {
        "structural": diagnose_musicxml(generated_musicxml).__dict__,
        "accuracy": None,
    }

    if reference_musicxml:
        ref_diag = diagnose_musicxml(reference_musicxml).__dict__
        result["reference_structural"] = ref_diag

        # Compare note counts
        gen_notes = result["structural"]["total_note_count"]
        ref_notes = ref_diag["total_note_count"]
        result["note_count_ratio"] = gen_notes / ref_notes if ref_notes > 0 else None

        # Compare measure counts
        gen_measures = result["structural"]["measure_count"]
        ref_measures = ref_diag["measure_count"]
        result["measure_count_ratio"] = gen_measures / ref_measures if ref_measures > 0 else None

        # Tie comparison
        gen_ties = result["structural"]["tie_count"]
        ref_ties = ref_diag["tie_count"]
        result["tie_ratio"] = gen_ties / ref_ties if ref_ties > 0 else None

    return result


def run_notation_evaluation(manifest_path: str, output_dir: str) -> dict[str, Any]:
    """Run notation evaluation on all clips in a manifest."""
    manifest = CorpusManifest.from_file(manifest_path)
    results = []

    for clip in manifest.clips:
        if not clip.reference_musicxml:
            continue

        print(f"Evaluating {clip.id}...")

        # Check if fixtures exist
        if not os.path.isfile(clip.audio):
            print(f"  Skipping {clip.id}: audio missing")
            continue

        try:
            # Read reference MusicXML
            with open(clip.reference_musicxml, "rb") as f:
                ref_xml = f.read()

            # For now, use reference MIDI → notation (isolates notation quality)
            if clip.reference_midi and os.path.isfile(clip.reference_midi):
                with open(clip.reference_midi, "rb") as f:
                    ref_midi = f.read()

                # Run production notation pipeline
                from music_features import notation_midi_from_performance, notation_with_engine

                pm = pretty_midi.PrettyMIDI(clip.reference_midi)
                total_time = pm.get_end_time()
                tempo_times, tempos = pm.get_tempo_changes()
                bpm = float(tempos[0]) if len(tempos) > 0 else 120.0
                beat_interval = 60.0 / bpm
                beat_times = list(range(0, int(total_time / beat_interval) + 1))
                beat_times = [t * beat_interval for t in beat_times]

                notation_midi, _ = notation_midi_from_performance(ref_midi, beat_times)
                result = notation_with_engine(notation_midi, beat_times)
                gen_xml = result.get("musicxml", b"")

                if gen_xml:
                    eval_result = evaluate_notation(gen_xml, ref_xml, ref_midi)
                    eval_result["clip_id"] = clip.id
                    eval_result["source_id"] = clip.source_id
                    results.append(eval_result)
                    gen_notes = eval_result["structural"]["total_note_count"]
                    ref_notes = eval_result.get(
                        "reference_structural", {}
                    ).get("total_note_count", "?")
                    gen_meas = eval_result["structural"]["measure_count"]
                    ref_meas = eval_result.get(
                        "reference_structural", {}
                    ).get("measure_count", "?")
                    gen_ties = eval_result["structural"]["tie_count"]
                    ref_ties = eval_result.get(
                        "reference_structural", {}
                    ).get("tie_count", "?")
                    print(f"  Notes: {gen_notes} (ref: {ref_notes})")
                    print(f"  Measures: {gen_meas} (ref: {ref_meas})")
                    print(f"  Ties: {gen_ties} (ref: {ref_ties})")

        except Exception as e:
            print(f"  Error: {e}")
            results.append({"clip_id": clip.id, "error": str(e)})

    # Save results
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, "notation_eval.json")
    with open(output_path, "w") as f:
        json.dump({"clips": results}, f, indent=2)
    print(f"\nResults saved to {output_path}")

    return {"clips": results}


def main():
    parser = argparse.ArgumentParser(description="Evaluate notation quality")
    parser.add_argument("--manifest", required=True, help="Path to corpus manifest")
    parser.add_argument(
        "--output-dir", default="evaluation/results/notation", help="Output directory"
    )
    args = parser.parse_args()

    run_notation_evaluation(args.manifest, args.output_dir)


if __name__ == "__main__":
    main()
