"""Evaluation harmony must not revive withheld cadence claims."""

from __future__ import annotations

import io

import pytest

pytest.importorskip("music21", reason="music21 not installed")

import pretty_midi  # noqa: E402

from evaluation.engines.harmony import Music21HarmonyAdapter  # noqa: E402


def _dominant_tonic_midi() -> bytes:
    midi = pretty_midi.PrettyMIDI(initial_tempo=120.0)
    piano = pretty_midi.Instrument(program=0)

    for pitch in (55, 59, 62):  # G-B-D, V in C major
        piano.notes.append(pretty_midi.Note(velocity=90, pitch=pitch, start=0.0, end=1.0))
    for pitch in (60, 64, 67):  # C-E-G, I in C major
        piano.notes.append(pretty_midi.Note(velocity=90, pitch=pitch, start=1.0, end=3.0))

    midi.instruments.append(piano)
    buffer = io.BytesIO()
    midi.write(buffer)
    return buffer.getvalue()


def test_evaluation_adapter_abstains_on_textbook_v_i() -> None:
    result = Music21HarmonyAdapter().analyze_harmony(_dominant_tonic_midi())

    # The fixture intentionally contains the progression the retired evaluator
    # used to call an authentic cadence. Evaluation must preserve the production
    # withholding decision rather than manufacture a cadence benchmark result.
    assert result["cadences"] == []


def test_adapter_metadata_does_not_claim_cadence_support() -> None:
    notes = Music21HarmonyAdapter.engine_info.notes.lower()

    assert "cadence is withheld" in notes
