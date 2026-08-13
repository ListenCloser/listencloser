"""Tests that Basic Pitch note evidence is preserved, not discarded."""

from __future__ import annotations

import pytest


def test_transcribe_preserves_model_note_events():
    pytest.importorskip("basic_pitch", reason="basic-pitch not installed")
    import music_features as mf

    audio = open("../tests/fixtures/real-piano.m4a", "rb").read()  # noqa: SIM115
    result = mf.transcribe_audio(audio, fmt="m4a")

    assert "model_note_events" in result
    events = result["model_note_events"]
    assert len(events) == result["num_notes"]

    # Every note event carries pitch/onset/offset/amplitude evidence.
    for ev in events:
        assert "pitch" in ev
        assert "start" in ev
        assert "end" in ev
        assert "amplitude" in ev
        assert 0.0 <= ev["amplitude"] <= 1.0

    # Amplitude (mean note-frame activation, NOT a probability) is attached to
    # the canonical notes where the onset round-trip maps cleanly.
    amplitudes = [n["amplitude"] for n in result["notes"] if n.get("amplitude") is not None]
    assert amplitudes, "expected amplitude evidence on canonical notes"


def test_note_entity_carries_amplitude():
    from domain.models import NoteEntity

    note = NoteEntity(pitch=60, start_seconds=0.0, end_seconds=0.5, velocity=64, amplitude=0.482)
    assert note.amplitude == pytest.approx(0.482)
    assert NoteEntity(pitch=60, start_seconds=0.0, end_seconds=0.5).amplitude is None


def test_migration_adds_note_amplitude():
    import pathlib

    migrations = pathlib.Path("../supabase/migrations")
    found = any("note_amplitude" in p.read_text() for p in migrations.glob("*.sql"))
    assert found, "expected a migration adding the note_amplitude column"
