"""Generate score screenshots for both engines at identical viewport."""

from __future__ import annotations

import io
import os
import tempfile
from pathlib import Path

import music21
from music_features import (
    transcribe_with_engine,
    decode_audio_to_wav,
    estimate_beats_with_engine,
    notation_with_engine,
)

OUTPUT_DIR = Path("/Users/giancarloricci/hello-ai/backend/evaluation/reports/engine_comparison")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

FIXTURE_PATH = Path("/Users/giancarloricci/hello-ai/tests/fixtures/real-piano.m4a")

# Configure music21
music21.environment.set("autoDownload", "allow")


def _generate_score_png(musicxml_bytes: bytes, notation_midi_bytes: bytes, out_path: Path) -> None:
    """Generate first-page score PNG using music21 from notation MIDI."""
    try:
        # Parse from notation MIDI (which is already quantized)
        score = music21.converter.parse(io.BytesIO(notation_midi_bytes))
        score.write("musicxml.png", fp=str(out_path))
    except Exception as e:
        print(f"  Score render from MIDI failed: {e}")
        # Fallback: try from musicxml
        try:
            score = music21.converter.parse(io.BytesIO(musicxml_bytes))
            score.write("musicxml.png", fp=str(out_path))
        except Exception as e2:
            print(f"  Score render from MusicXML also failed: {e2}")
            out_path.with_suffix(".musicxml").write_bytes(musicxml_bytes)


def main() -> None:
    import io

    audio_bytes = FIXTURE_PATH.read_bytes()
    print(f"Loaded {len(audio_bytes)} bytes from {FIXTURE_PATH}")

    for profile, label in [("general", "Basic Pitch"), ("solo_piano", "Transkun")]:
        print(f"\n=== {label} ({profile}) ===")
        tr = transcribe_with_engine(audio_bytes, profile=profile)
        print(f"  transcription: {tr['num_notes']} notes, engine={tr['provenance']['engine']}")
        
        wav = decode_audio_to_wav(audio_bytes, fmt="m4a")
        beats = estimate_beats_with_engine(wav)
        beat_times = beats.get("beats", [])
        
        notation = notation_with_engine(tr["midi"], beat_times, piano_grand_staff=True, adaptive=True)
        print(f"  notation: musicxml={len(notation['musicxml'])} bytes")
        
        # Generate score screenshot
        out_path = OUTPUT_DIR / f"{label.lower().replace(' ', '_')}_score.png"
        print(f"  rendering score to {out_path}...")
        _generate_score_png(notation["musicxml"], notation["notation_midi"], out_path)
        
        if out_path.exists():
            print(f"  score PNG generated: {out_path.stat().st_size} bytes")
        elif out_path.with_suffix(".musicxml").exists():
            print(f"  score PNG failed, musicxml saved instead")
    
    print(f"\nOutput dir: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()