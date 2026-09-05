from __future__ import annotations

import hashlib
import io
from pathlib import Path

import pretty_midi
import pytest

from engines.melody.midibert_engine import MidiBERTMelodyEngine


def _midi_bytes() -> bytes:
    midi = pretty_midi.PrettyMIDI(initial_tempo=120)
    piano = pretty_midi.Instrument(program=0)
    piano.notes.extend(
        [
            pretty_midi.Note(velocity=81, pitch=60, start=0.13, end=0.47),
            pretty_midi.Note(velocity=92, pitch=64, start=0.61, end=1.02),
            pretty_midi.Note(velocity=73, pitch=67, start=1.19, end=1.88),
        ]
    )
    midi.instruments.append(piano)
    buffer = io.BytesIO()
    midi.write(buffer)
    return buffer.getvalue()


def _runtime(tmp_path: Path) -> tuple[Path, Path, Path, str]:
    root = tmp_path / "midibert"
    for relative in (
        "melody_extraction/midibert/extract.py",
        "melody_extraction/midibert/midi2CP.py",
        "MidiBERT/model.py",
    ):
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("# pinned source fixture\n")
    dict_file = root / "data_creation/prepare_data/dict/CP.pkl"
    dict_file.parent.mkdir(parents=True, exist_ok=True)
    dict_file.write_bytes(b"dict-fixture")
    checkpoint = tmp_path / "model_best.ckpt"
    checkpoint.write_bytes(b"checkpoint-fixture")
    checksum = hashlib.sha256(checkpoint.read_bytes()).hexdigest()
    return root, checkpoint, dict_file, checksum


def test_midibert_requires_pinned_checkpoint_checksum(tmp_path: Path):
    root, checkpoint, dict_file, _ = _runtime(tmp_path)
    engine = MidiBERTMelodyEngine(
        root=str(root), checkpoint=str(checkpoint), dict_file=str(dict_file)
    )
    with pytest.raises(RuntimeError, match="SHA-256 is not pinned"):
        engine._validate_runtime()


def test_midibert_rejects_wrong_checkpoint_checksum(tmp_path: Path):
    root, checkpoint, dict_file, _ = _runtime(tmp_path)
    engine = MidiBERTMelodyEngine(
        root=str(root),
        checkpoint=str(checkpoint),
        dict_file=str(dict_file),
        checkpoint_sha256="0" * 64,
    )
    with pytest.raises(RuntimeError, match="checksum mismatch"):
        engine._validate_runtime()


def test_midibert_publishes_exact_source_note_times_and_native_classes(
    tmp_path: Path, monkeypatch
):
    root, checkpoint, dict_file, checksum = _runtime(tmp_path)
    engine = MidiBERTMelodyEngine(
        root=str(root),
        checkpoint=str(checkpoint),
        dict_file=str(dict_file),
        checkpoint_sha256=checksum,
    )
    monkeypatch.setattr(engine, "_predict_classes", lambda _path: [1, 3, 2])

    result = engine.analyze(_midi_bytes())

    assert result.provenance.engine == "midibert"
    assert result.provenance.parameters["checkpoint_sha256"] == checksum
    assert result.melody is not None
    assert result.melody["candidate_note_count"] == 3
    assert result.melody["selected_note_count"] == 2
    notes = result.melody["notes"]
    assert [note["pitch"] for note in notes] == [60, 67]
    assert [note["model_class"] for note in notes] == ["melody", "bridge"]
    assert notes[0]["start_seconds"] == pytest.approx(0.13, abs=0.01)
    assert notes[0]["end_seconds"] == pytest.approx(0.47, abs=0.01)
    assert notes[1]["start_seconds"] == pytest.approx(1.19, abs=0.01)
    assert notes[1]["end_seconds"] == pytest.approx(1.88, abs=0.01)


def test_midibert_fails_closed_when_label_count_does_not_match_source(
    tmp_path: Path, monkeypatch
):
    root, checkpoint, dict_file, checksum = _runtime(tmp_path)
    engine = MidiBERTMelodyEngine(
        root=str(root),
        checkpoint=str(checkpoint),
        dict_file=str(dict_file),
        checkpoint_sha256=checksum,
    )
    monkeypatch.setattr(engine, "_predict_classes", lambda _path: [1, 2])

    with pytest.raises(RuntimeError, match="note-label count"):
        engine.analyze(_midi_bytes())
