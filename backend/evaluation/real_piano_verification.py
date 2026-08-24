"""Real-piano production verification.

Tests both Basic Pitch and Transkun transcription paths,
then runs LStoM melody extraction on each.

Reports: total notes, melody notes, pitch range, continuity,
contamination, runtime, failures.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

import pretty_midi

from engines.melody.lstom_engine import LStoMMelodyEngine
from engines.registry import get_transcription_engine

AUDIO_PATH = Path(__file__).resolve().parent.parent.parent / "tests" / "fixtures" / "real-piano.m4a"

# Also check backend/tests/fixtures
if not AUDIO_PATH.exists():
    AUDIO_PATH = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "real-piano.m4a"


def evaluate_melody(melody: dict | None, label: str) -> dict:
    """Evaluate a melody result."""
    if melody is None:
        return {"status": "no_melody", "label": label}

    low = melody.get("low_pitch", 0)
    high = melody.get("high_pitch", 127)
    range_semi = melody.get("range_semitones", 0)
    stepwise = melody.get("stepwise_ratio", 0)
    quality = melody.get("quality_score", 0)

    contamination = "clean" if low >= 48 else "contaminated"
    continuity = "continuous" if stepwise > 0.1 else "discontinuous"

    return {
        "status": "ok",
        "label": label,
        "low_pitch": low,
        "high_pitch": high,
        "range_semitones": range_semi,
        "stepwise_ratio": stepwise,
        "quality_score": quality,
        "contamination_risk": contamination,
        "continuity": continuity,
    }


def run_transcription_and_melody(engine_name: str) -> dict:
    """Run transcription + melody extraction pipeline."""
    print(f"\n{'='*60}")
    print(f"Testing: {engine_name} transcription → LStoM melody")
    print(f"{'='*60}")

    audio_bytes = AUDIO_PATH.read_bytes()

    # Transcription
    t0 = time.perf_counter()
    try:
        engine = get_transcription_engine(engine_name)
        result = engine.transcribe(audio_bytes, fmt="midi")
        midi_bytes = result.midi
        transcription_ms = round((time.perf_counter() - t0) * 1000)
        print(f"  Transcription: OK ({transcription_ms}ms)")
    except Exception as e:
        transcription_ms = round((time.perf_counter() - t0) * 1000)
        print(f"  Transcription: FAILED ({transcription_ms}ms) - {e}")
        return {
            "engine": engine_name,
            "transcription_status": "failed",
            "transcription_error": str(e),
            "transcription_ms": transcription_ms,
        }

    # Parse MIDI to get note count
    try:
        pm = pretty_midi.PrettyMIDI(__import__("io").BytesIO(midi_bytes))
        total_notes = sum(len(inst.notes) for inst in pm.instruments if not inst.is_drum)
    except Exception:
        total_notes = 0

    print(f"  Total notes: {total_notes}")

    # Melody extraction
    t1 = time.perf_counter()
    try:
        lstom = LStoMMelodyEngine()
        melody_result = lstom.analyze(midi_bytes)
        melody_ms = round((time.perf_counter() - t1) * 1000)
        print(f"  Melody extraction: OK ({melody_ms}ms)")
    except Exception as e:
        melody_ms = round((time.perf_counter() - t1) * 1000)
        print(f"  Melody extraction: FAILED ({melody_ms}ms) - {e}")
        return {
            "engine": engine_name,
            "transcription_status": "ok",
            "transcription_ms": transcription_ms,
            "total_notes": total_notes,
            "melody_status": "failed",
            "melody_error": str(e),
            "melody_ms": melody_ms,
        }

    # Evaluate melody
    melody = melody_result.melody
    eval_result = evaluate_melody(melody, engine_name)

    if melody:
        print(f"  Melody notes: ~{int(melody['quality_score'] * total_notes)}")
        print(
            f"  Pitch range: {melody['low_pitch']}-{melody['high_pitch']} "
            f"({melody['range_semitones']} semitones)"
        )
        print(f"  Stepwise ratio: {melody['stepwise_ratio']}")
        print(f"  Quality score: {melody['quality_score']}")
        print(f"  Contamination: {eval_result['contamination_risk']}")
        print(f"  Continuity: {eval_result['continuity']}")
    else:
        print("  Melody: None")

    return {
        "engine": engine_name,
        "transcription_status": "ok",
        "transcription_ms": transcription_ms,
        "total_notes": total_notes,
        "melody_status": "ok" if melody else "no_melody",
        "melody_ms": melody_ms,
        "melody_eval": eval_result,
        "provenance": melody_result.provenance.to_dict() if melody else None,
    }


def main():
    print(f"Audio file: {AUDIO_PATH}")
    print(f"File size: {AUDIO_PATH.stat().st_size / 1024:.1f} KB")

    results = []

    # Test Basic Pitch
    results.append(run_transcription_and_melody("basic_pitch"))

    # Test Transkun
    results.append(run_transcription_and_melody("transkun"))

    # Summary
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")

    for r in results:
        engine = r["engine"]
        t_status = r.get("transcription_status", "unknown")
        m_status = r.get("melody_status", "unknown")
        t_ms = r.get("transcription_ms", "?")
        m_ms = r.get("melody_ms", "?")
        total = r.get("total_notes", "?")

        if m_status == "ok" and "melody_eval" in r:
            me = r["melody_eval"]
            print(f"\n{engine}:")
            print(f"  Transcription: {t_status} ({t_ms}ms)")
            print(f"  Total notes: {total}")
            print(f"  Melody: {m_status} ({m_ms}ms)")
            print(f"  Contamination: {me.get('contamination_risk', '?')}")
            print(f"  Continuity: {me.get('continuity', '?')}")
            print(f"  Pitch range: {me.get('range_semitones', '?')} semitones")
        else:
            print(f"\n{engine}:")
            print(f"  Transcription: {t_status} ({t_ms}ms)")
            print(f"  Melody: {m_status}")
            if "melody_error" in r:
                print(f"  Error: {r['melody_error']}")

    # Save results
    output_path = Path(__file__).resolve().parent / "real_piano_results.json"
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nResults saved to: {output_path}")


if __name__ == "__main__":
    main()
