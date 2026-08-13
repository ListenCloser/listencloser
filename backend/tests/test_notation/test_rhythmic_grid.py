"""Tests for evidence-based rhythmic grid selection."""

from __future__ import annotations

import io

import pytest

pytest.importorskip("pretty_midi", reason="pretty_midi not installed locally")

import pretty_midi  # noqa: E402

from notation.metrics import musicxml_metrics  # noqa: E402
from notation.quantize import quantize_rhythmic_grid  # noqa: E402
from tests.fixtures.rhythmic import (  # noqa: E402
    dotted_rhythm,
    sixteenth_notes,
    straight_eighths,
    triplet_eighths,
)


def _selected_grid(midi_bytes: bytes) -> str:
    _out, report = quantize_rhythmic_grid(midi_bytes)
    return report["selected_grid"]


def _note_count(midi_bytes: bytes) -> int:
    midi = pretty_midi.PrettyMIDI(io.BytesIO(midi_bytes))
    return sum(len(i.notes) for i in midi.instruments if not i.is_drum)


class TestSubdivisionSelection:
    def test_straight_eighths_selects_eighth(self):
        assert _selected_grid(straight_eighths()) == "eighth"

    def test_sixteenths_select_sixteenth(self):
        assert _selected_grid(sixteenth_notes()) == "sixteenth"

    def test_triplets_select_triplet_eighth(self):
        assert _selected_grid(triplet_eighths()) == "triplet_eighth"

    def test_dotted_rhythm_selects_sixteenth(self):
        assert _selected_grid(dotted_rhythm()) == "sixteenth"


class TestTimingBounds:
    def test_onset_displacement_stays_bounded(self):
        """A correctly selected grid keeps onset displacement small."""
        for midi in (straight_eighths(), sixteenth_notes(), triplet_eighths(), dotted_rhythm()):
            _out, report = quantize_rhythmic_grid(midi)
            step = report["grid_step_seconds"]
            assert report["onset_shift_p95"] <= step / 2 + 1e-6
            assert report["duration_shift_p95"] <= step + 1e-6

    def test_note_count_preserved(self):
        for midi in (straight_eighths(), sixteenth_notes(), triplet_eighths(), dotted_rhythm()):
            before = _note_count(midi)
            out, _report = quantize_rhythmic_grid(midi)
            assert _note_count(out) == before


class TestMetrics:
    def test_musicxml_metrics_counts_structure(self):
        import music_features as mf

        xml = mf.convert_format(
            quantize_rhythmic_grid(sixteenth_notes())[0], "midi", "musicxml", notation_ready=True
        ).decode("utf-8", errors="replace")
        metrics = musicxml_metrics(xml)
        assert metrics["measure_count"] >= 1
        assert metrics["note_count"] == 16
        assert metrics["distinct_duration_count"] > 0
        # Clean sixteenth-note fixture should have no ties or tuplets.
        assert metrics["tie_element_count"] == 0
        assert metrics["tuplet_count"] == 0

    def test_triplet_fixture_produces_tuplets(self):
        import music_features as mf

        xml = mf.convert_format(
            quantize_rhythmic_grid(triplet_eighths())[0], "midi", "musicxml", notation_ready=True
        ).decode("utf-8", errors="replace")
        metrics = musicxml_metrics(xml)
        # Triplets in notation appear as <time-modification>.
        assert metrics["tuplet_count"] > 0
