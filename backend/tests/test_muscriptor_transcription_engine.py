"""Focused tests for the isolated MuScriptor transcription challenger."""

from __future__ import annotations

import base64
import hashlib
import subprocess

import pytest

from engines.registry import get_transcription_engine
from engines.transcription.muscriptor import MuScriptorEngine

_ONE_NOTE_MIDI = base64.b64decode("TVRoZAAAAAYAAAABAeBNVHJrAAAAEADAAACQPECDYIA8QAD/LwA=")


def _runtime_files(tmp_path):
    runtime = tmp_path / "python"
    runtime.write_text("placeholder", encoding="utf-8")
    checkpoint = tmp_path / "model.safetensors"
    checkpoint.write_bytes(b"pinned-muscriptor-small")
    checksum = hashlib.sha256(checkpoint.read_bytes()).hexdigest()
    return runtime, checkpoint, checksum


def test_registry_exposes_muscriptor_only_by_explicit_selection():
    engine = get_transcription_engine("muscriptor")
    assert isinstance(engine, MuScriptorEngine)
    assert engine.provenance.engine == "muscriptor"
    assert engine.provenance.parameters["commercial_default_eligible"] is False
    assert engine.provenance.parameters["weight_license"] == "CC-BY-NC-4.0"


def test_muscriptor_requires_pinned_checkpoint_hash(tmp_path):
    runtime, checkpoint, _ = _runtime_files(tmp_path)
    engine = MuScriptorEngine(
        runtime_python=str(runtime),
        model_path=str(checkpoint),
    )

    with pytest.raises(RuntimeError, match="MUSCRIPTOR_MODEL_SHA256"):
        engine.transcribe(b"RIFF-not-real-audio", fmt="wav")


def test_muscriptor_rejects_checkpoint_hash_mismatch(tmp_path):
    runtime, checkpoint, _ = _runtime_files(tmp_path)
    engine = MuScriptorEngine(
        runtime_python=str(runtime),
        model_path=str(checkpoint),
        model_sha256="0" * 64,
    )

    with pytest.raises(RuntimeError, match="SHA-256 mismatch"):
        engine.transcribe(b"RIFF-not-real-audio", fmt="wav")


def test_muscriptor_runs_offline_child_and_normalizes_midi(tmp_path, monkeypatch):
    runtime, checkpoint, checksum = _runtime_files(tmp_path)
    observed = {}

    def fake_run(command, **kwargs):
        observed["command"] = command
        observed["env"] = kwargs["env"]
        output_path = command[command.index("--output") + 1]
        with open(output_path, "wb") as handle:
            handle.write(_ONE_NOTE_MIDI)
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    engine = MuScriptorEngine(
        runtime_python=str(runtime),
        model_path=str(checkpoint),
        model_sha256=checksum,
        device="cpu",
    )

    result = engine.transcribe(b"RIFF-not-real-audio", fmt="wav")

    assert observed["command"][:4] == [
        str(runtime),
        "-m",
        "muscriptor",
        "transcribe",
    ]
    assert observed["command"][observed["command"].index("--model") + 1] == str(checkpoint)
    assert observed["command"][observed["command"].index("--device") + 1] == "cpu"
    assert observed["command"][observed["command"].index("--detect-tempo") + 1] == "false"
    assert observed["env"]["HF_HUB_OFFLINE"] == "1"
    assert result.midi == _ONE_NOTE_MIDI
    assert result.num_notes == 1
    assert result.notes[0]["pitch"] == 60
    assert result.model_note_events[0]["instrument_name"] == "Acoustic Grand Piano"
    assert result.tempo_is_placeholder is True
    assert result.meter_is_placeholder is True
    assert result.supports_meter is False
    assert result.provenance.parameters["checkpoint_sha256"] == checksum


def test_muscriptor_failure_does_not_fallback(tmp_path, monkeypatch):
    runtime, checkpoint, checksum = _runtime_files(tmp_path)

    def fake_run(command, **kwargs):
        return subprocess.CompletedProcess(command, 9, stdout="", stderr="model failed")

    monkeypatch.setattr(subprocess, "run", fake_run)
    engine = MuScriptorEngine(
        runtime_python=str(runtime),
        model_path=str(checkpoint),
        model_sha256=checksum,
    )

    with pytest.raises(RuntimeError, match="isolated runtime failed"):
        engine.transcribe(b"RIFF-not-real-audio", fmt="wav")
