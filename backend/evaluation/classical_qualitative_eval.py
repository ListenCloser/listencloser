"""Qualitative evaluation of LStoM vs Skyline on classical piano MIDI.

This is NOT quantitative accuracy — no ground-truth melody labels exist for
classical piano. Instead, this protocol measures:
- Contamination: does the engine pick up bass/accompaniment notes?
- Continuity: does the extracted melody form a coherent line?
- Pitch range: is the melody in a reasonable treble range?
- Note fraction: what fraction of notes are selected as melody?

Evaluation criteria (qualitative, not quantitative):
- Contamination: melody low_pitch should be >= MIDI 48 (C3)
- Range: melody should span 5-60 semitones (1-5 octaves)
- Continuity: stepwise_ratio should be reasonable (>0.1)
- Note fraction: quality_score should be 0.05-0.5 (not too few, not too many)

Usage:
    python classical_qualitative_eval.py
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

import pretty_midi

from engines.melody.lstom_engine import LStoMMelodyEngine
from engines.melody.skyline_engine import SkylineMelodyEngine

ASAP_DIR = Path(os.environ.get("ASAP_DIR", "/Users/giancarloricci/MUSIC_EVAL_CACHE_DIR/asap"))

# Select 25 classical piano pieces: score MIDI files from diverse composers
CLASSICAL_PIECES = [
    # Mozart
    "Mozart/Fantasie_475/midi_score.mid",
    "Mozart/Piano_Sonatas/12-1/midi_score.mid",
    "Mozart/Piano_Sonatas/12-2/midi_score.mid",
    "Mozart/Piano_Sonatas/12-3/midi_score.mid",
    "Mozart/Piano_Sonatas/8-1/midi_score.mid",
    # Chopin
    "Chopin/Etudes_op_10/3/midi_score.mid",
    "Chopin/Etudes_op_10/5/midi_score.mid",
    "Chopin/Etudes_op_10/12/midi_score.mid",
    "Chopin/Ballades/1/midi_score.mid",
    "Chopin/Nocturnes/9_2/midi_score.mid",
    "Chopin/Scherzos/20/midi_score.mid",
    "Chopin/Berceuse_op_57/midi_score.mid",
    "Chopin/Barcarolle/midi_score.mid",
    # Beethoven
    "Beethoven/Piano_Sonatas_1/midi_score.mid",
    "Beethoven/Piano_Sonatas_14_2/midi_score.mid",
    "Beethoven/Piano_Sonatas_29_3/midi_score.mid",
    # Schubert
    "Schubert/Wanderer_Fantasie/midi_score.mid",
    # Liszt
    "Liszt/Consolations/midi_score.mid",
    # Haydn
    "Haydn/Sonatas/Hob_XVI_34_1/midi_score.mid",
    "Haydn/Sonatas/Hob_XVI_37_1/midi_score.mid",
    # Schumann
    "Schumann/Kreisleriana/midi_score.mid",
    # Debussy
    "Debussy/Debussy_Ca/midi_score.mid",
    # Rachmaninoff
    "Rachmaninoff/Prelude_3_2/midi_score.mid",
    # Grieg
    "Grieg/Lyric/midi_score.mid",
    # Prokofiev
    "Prokofiev/Sarcasms/midi_score.mid",
]


def evaluate_melody(melody: dict | None, engine_name: str, piece: str) -> dict:
    """Evaluate a melody result on qualitative criteria."""
    if melody is None:
        return {
            "piece": piece,
            "engine": engine_name,
            "status": "no_melody",
            "contamination_risk": "unknown",
            "continuity": "unknown",
            "pitch_range": "unknown",
            "note_fraction": "unknown",
        }

    low = melody.get("low_pitch", 0)
    high = melody.get("high_pitch", 127)
    range_semi = melody.get("range_semitones", 0)
    stepwise = melody.get("stepwise_ratio", 0)
    quality = melody.get("quality_score", 0)

    # Contamination: melody should not extend into bass range (below C3=48)
    contamination = "clean" if low >= 48 else "contaminated"

    # Continuity: stepwise ratio should be > 0.1 for a coherent melody
    continuity = "continuous" if stepwise > 0.1 else "discontinuous"

    # Pitch range: should be 5-60 semitones
    pitch_range = "reasonable" if 5 <= range_semi <= 60 else "unreasonable"

    # Note fraction: should be 0.05-0.5
    note_fraction = "reasonable" if 0.05 <= quality <= 0.5 else "unreasonable"

    return {
        "piece": piece,
        "engine": engine_name,
        "status": "ok",
        "low_pitch": low,
        "high_pitch": high,
        "range_semitones": range_semi,
        "stepwise_ratio": stepwise,
        "quality_score": quality,
        "contamination_risk": contamination,
        "continuity": continuity,
        "pitch_range": pitch_range,
        "note_fraction": note_fraction,
    }


def run_evaluation():
    """Run qualitative evaluation on classical piano pieces."""
    lstom = LStoMMelodyEngine()
    skyline = SkylineMelodyEngine()

    results = []
    available_pieces = []

    for piece in CLASSICAL_PIECES:
        midi_path = ASAP_DIR / piece
        if midi_path.exists():
            available_pieces.append(piece)
        else:
            print(f"  SKIP (not found): {piece}")

    print(f"\nFound {len(available_pieces)}/{len(CLASSICAL_PIECES)} pieces\n")

    for piece in available_pieces:
        midi_path = ASAP_DIR / piece
        midi_bytes = midi_path.read_bytes()

        # Get note count
        try:
            pm = pretty_midi.PrettyMIDI(str(midi_path))
            note_count = sum(len(inst.notes) for inst in pm.instruments if not inst.is_drum)
        except Exception:
            note_count = 0

        # LStoM
        lstom_result = lstom.analyze(midi_bytes)
        lstom_eval = evaluate_melody(lstom_result.melody, "lstom", piece)
        lstom_eval["note_count"] = note_count
        results.append(lstom_eval)

        # Skyline
        skyline_result = skyline.analyze(midi_bytes)
        skyline_eval = evaluate_melody(skyline_result.melody, "skyline", piece)
        skyline_eval["note_count"] = note_count
        results.append(skyline_eval)

        # Summary line
        lstom_status = lstom_eval["status"]
        skyline_status = skyline_eval["status"]
        if lstom_status == "ok" and skyline_status == "ok":
            l_contam = lstom_eval["contamination_risk"]
            s_contam = skyline_eval["contamination_risk"]
            l_range = lstom_eval["range_semitones"]
            s_range = skyline_eval["range_semitones"]
            print(
                f"  {piece}: {note_count} notes | "
                f"LStoM: {l_contam}, {l_range}semi | "
                f"Skyline: {s_contam}, {s_range}semi"
            )
        else:
            print(
                f"  {piece}: {note_count} notes | "
                f"LStoM: {lstom_status} | Skyline: {skyline_status}"
            )

    # Summary statistics
    lstom_results = [r for r in results if r["engine"] == "lstom" and r["status"] == "ok"]
    skyline_results = [r for r in results if r["engine"] == "skyline" and r["status"] == "ok"]

    print(f"\n{'='*80}")
    print("QUALITATIVE EVALUATION SUMMARY")
    print(f"{'='*80}")
    print(f"\nPieces evaluated: {len(available_pieces)}")
    print(f"LStoM successful: {len(lstom_results)}/{len(available_pieces)}")
    print(f"Skyline successful: {len(skyline_results)}/{len(available_pieces)}")

    if lstom_results:
        lstom_contam = sum(1 for r in lstom_results if r["contamination_risk"] == "contaminated")
        lstom_continuous = sum(1 for r in lstom_results if r["continuity"] == "continuous")
        lstom_ranges = [r["range_semitones"] for r in lstom_results]
        lstom_lows = [r["low_pitch"] for r in lstom_results]
        n = len(lstom_results)
        print("\nLStoM:")
        print(f"  Contamination: {lstom_contam}/{n} ({lstom_contam/n*100:.0f}%)")
        print(f"  Continuity: {lstom_continuous}/{n} ({lstom_continuous/n*100:.0f}%)")
        print(
            f"  Pitch range: {min(lstom_ranges)}-{max(lstom_ranges)} semitones "
            f"(mean {sum(lstom_ranges)/n:.1f})"
        )
        print(
            f"  Low pitch: {min(lstom_lows)}-{max(lstom_lows)} " f"(mean {sum(lstom_lows)/n:.1f})"
        )

    if skyline_results:
        sky_contam = sum(1 for r in skyline_results if r["contamination_risk"] == "contaminated")
        sky_continuous = sum(1 for r in skyline_results if r["continuity"] == "continuous")
        sky_ranges = [r["range_semitones"] for r in skyline_results]
        sky_lows = [r["low_pitch"] for r in skyline_results]
        ns = len(skyline_results)
        print("\nSkyline:")
        print(f"  Contamination: {sky_contam}/{ns} ({sky_contam/ns*100:.0f}%)")
        print(f"  Continuity: {sky_continuous}/{ns} ({sky_continuous/ns*100:.0f}%)")
        print(
            f"  Pitch range: {min(sky_ranges)}-{max(sky_ranges)} semitones "
            f"(mean {sum(sky_ranges)/ns:.1f})"
        )
        print(f"  Low pitch: {min(sky_lows)}-{max(sky_lows)} " f"(mean {sum(sky_lows)/ns:.1f})")

    print(f"\n{'='*80}")
    print("NOTE: This is qualitative evaluation, NOT quantitative accuracy.")
    print("No public classical melody extraction ground truth exists.")
    print("Criteria: contamination (bass pickup), continuity, pitch range.")
    print(f"{'='*80}")

    # Save results
    output_path = Path(__file__).resolve().parent / "classical_qualitative_results.json"
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nDetailed results saved to: {output_path}")

    return results


if __name__ == "__main__":
    run_evaluation()
