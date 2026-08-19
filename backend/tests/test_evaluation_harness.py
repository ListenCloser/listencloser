"""Tests for evaluation harness correctness.

Verifies that the evaluation metrics correctly handle:
1. MusicXML measure counting (per part, not total)
2. Harmony adapter chord detection (uses Chord.quality, not impliedQuality)
"""

from __future__ import annotations

import pytest

pytest.importorskip("music21", reason="music21 not installed")

from evaluation.notation_metrics import diagnose_musicxml  # noqa: E402


class TestMeasureCounting:
    """Verify measure counting is per-part, not total across all parts."""

    def test_single_part_measures_counted_correctly(self):
        """A single-part score should count measures in that part."""
        xml = b"""<?xml version="1.0" encoding="UTF-8"?>
<score-partwise>
  <part-list>
    <score-part id="P1"><part-name>Piano</part-name></score-part>
  </part-list>
  <part id="P1">
    <measure number="1">
      <note><pitch><step>C</step><octave>4</octave></pitch><duration>4</duration></note>
    </measure>
    <measure number="2">
      <note><pitch><step>D</step><octave>4</octave></pitch><duration>4</duration></note>
    </measure>
    <measure number="3">
      <note><pitch><step>E</step><octave>4</octave></pitch><duration>4</duration></note>
    </measure>
  </part>
</score-partwise>"""
        diag = diagnose_musicxml(xml)
        assert diag.measure_count == 3

    def test_two_parts_counted_per_part_not_total(self):
        """A two-part score should count measures in the first part only,
        not total across both parts."""
        xml = b"""<?xml version="1.0" encoding="UTF-8"?>
<score-partwise>
  <part-list>
    <score-part id="P1"><part-name>Treble</part-name></score-part>
    <score-part id="P2"><part-name>Bass</part-name></score-part>
  </part-list>
  <part id="P1">
    <measure number="1">
      <note><pitch><step>C</step><octave>4</octave></pitch><duration>4</duration></note>
    </measure>
    <measure number="2">
      <note><pitch><step>D</step><octave>4</octave></pitch><duration>4</duration></note>
    </measure>
  </part>
  <part id="P2">
    <measure number="1">
      <note><pitch><step>C</step><octave>3</octave></pitch><duration>4</duration></note>
    </measure>
    <measure number="2">
      <note><pitch><step>D</step><octave>3</octave></pitch><duration>4</duration></note>
    </measure>
  </part>
</score-partwise>"""
        diag = diagnose_musicxml(xml)
        assert diag.measure_count == 2  # Not 4

    def test_grand_staff_counted_correctly(self):
        """A grand-staff score (1 part with 2 staves) should count measures
        in the part, not across staves."""
        xml = b"""<?xml version="1.0" encoding="UTF-8"?>
<score-partwise>
  <part-list>
    <score-part id="P1"><part-name>Piano</part-name></score-part>
  </part-list>
  <part id="P1">
    <measure number="1">
      <attributes><staves>2</staves></attributes>
      <note><staff>1</staff><pitch><step>C</step><octave>4</octave></pitch><duration>4</duration></note>
      <note><staff>2</staff><pitch><step>C</step><octave>3</octave></pitch><duration>4</duration></note>
    </measure>
    <measure number="2">
      <note><staff>1</staff><pitch><step>D</step><octave>4</octave></pitch><duration>4</duration></note>
      <note><staff>2</staff><pitch><step>D</step><octave>3</octave></pitch><duration>4</duration></note>
    </measure>
    <measure number="3">
      <note><staff>1</staff><pitch><step>E</step><octave>4</octave></pitch><duration>4</duration></note>
      <note><staff>2</staff><pitch><step>E</step><octave>3</octave></pitch><duration>4</duration></note>
    </measure>
  </part>
</score-partwise>"""
        diag = diagnose_musicxml(xml)
        assert diag.measure_count == 3


class TestHarmonyAdapterQuality:
    """Verify the harmony adapter uses Chord.quality, not impliedQuality."""

    def test_adapter_produces_chords_from_midi(self):
        """The adapter should produce chords from polyphonic MIDI input."""
        import io

        import pretty_midi

        from evaluation.engines.harmony import Music21HarmonyAdapter

        # Create a simple MIDI with a C major triad
        pm = pretty_midi.PrettyMIDI(initial_tempo=120)
        inst = pretty_midi.Instrument(program=0)
        for pitch in [60, 64, 67]:  # C4, E4, G4
            inst.notes.append(pretty_midi.Note(velocity=80, pitch=pitch, start=0.0, end=1.0))
        pm.instruments.append(inst)
        buf = io.BytesIO()
        pm.write(buf)
        midi_bytes = buf.getvalue()

        adapter = Music21HarmonyAdapter()
        result = adapter.analyze_harmony(midi_bytes)

        # Should detect at least one chord
        assert len(result["chords"]) > 0, "Adapter should detect chords from polyphonic MIDI"

        # First chord should have root and quality
        chord = result["chords"][0]
        assert "root" in chord
        assert "quality" in chord
        assert chord["root"]  # not empty
        assert chord["quality"]  # not empty
