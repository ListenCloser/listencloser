"""Regression tests for chord detection.

Verifies that the production harmony engine detects chords from MIDI
input using `Chord.quality` (always available) instead of
`Chord.impliedQuality` (absent on MIDI-derived Chord objects).
"""

from __future__ import annotations

import io

import pytest

pytest.importorskip("music21", reason="music21 not installed")

import pretty_midi  # noqa: E402

from engines.harmony.music21_engine import Music21HarmonyEngine  # noqa: E402


def _polyphonic_midi_bytes() -> bytes:
    """Create a MIDI file with polyphonic content (C major triad)."""
    pm = pretty_midi.PrettyMIDI(initial_tempo=120)
    inst = pretty_midi.Instrument(program=0)
    # C major triad: C4, E4, G4
    for pitch in [60, 64, 67]:
        inst.notes.append(pretty_midi.Note(velocity=80, pitch=pitch, start=0.0, end=1.0))
    pm.instruments.append(inst)
    buf = io.BytesIO()
    pm.write(buf)
    return buf.getvalue()


def _monophonic_midi_bytes() -> bytes:
    """Create a MIDI file with monophonic content (single notes)."""
    pm = pretty_midi.PrettyMIDI(initial_tempo=120)
    inst = pretty_midi.Instrument(program=0)
    for i, pitch in enumerate([60, 62, 64, 65, 67]):
        inst.notes.append(
            pretty_midi.Note(velocity=80, pitch=pitch, start=i * 0.5, end=i * 0.5 + 0.4)
        )
    pm.instruments.append(inst)
    buf = io.BytesIO()
    pm.write(buf)
    return buf.getvalue()


class TestChordDetectionQuality:
    """Verify chord detection uses Chord.quality, not Chord.impliedQuality."""

    def test_polyphonic_midi_produces_chords(self):
        """Polyphonic MIDI (C major triad) should produce at least one chord."""
        engine = Music21HarmonyEngine()
        midi_bytes = _polyphonic_midi_bytes()
        result = engine.analyze(midi_bytes)
        # With the fix, polyphonic MIDI should produce chords
        assert len(result.chords) > 0, "Polyphonic MIDI should produce chords"

    def test_chord_has_root_and_quality(self):
        """Detected chords should have root and quality fields."""
        engine = Music21HarmonyEngine()
        midi_bytes = _polyphonic_midi_bytes()
        result = engine.analyze(midi_bytes)
        if result.chords:
            chord = result.chords[0]
            assert "root" in chord
            assert "quality" in chord
            assert chord["root"]  # not empty
            assert chord["quality"]  # not empty

    def test_chord_detection_on_real_piano_fixture(self):
        """Real-piano fixture should produce chords (regression test)."""
        try:
            from music_features import transcribe_with_engine

            with open("../tests/fixtures/real-piano.m4a", "rb") as f:
                audio_bytes = f.read()

            transcribe_result = transcribe_with_engine(audio_bytes, fmt="m4a", profile="auto")
            midi_bytes = transcribe_result["midi"]

            engine = Music21HarmonyEngine()
            result = engine.analyze(midi_bytes)
            assert len(result.chords) > 0, "Real-piano fixture should produce chords"
        except FileNotFoundError:
            pytest.skip("Real-piano fixture not available")
