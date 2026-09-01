from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path

import pretty_midi
import pytest

from engines.registry import get_transcription_engine
from engines.transcription.tsumugi import TsumugiEngine


def _runtime_paths(tmp_path: Path) -> tuple[Path, Path, Path]:
    source_root = tmp_path / "tsumugi"
    module_path = source_root / TsumugiEngine.MODULE_PATH
    module_path.parent.mkdir(parents=True)
    module_path.write_text("# test module\n")

    python = source_root / ".venv" / "bin" / "python"
    python.parent.mkdir(parents=True)
    python.write_text("#!/bin/sh\n")
    python.chmod(0o755)

    checkpoint = tmp_path / "tsumugi.ckpt"
    checkpoint.write_bytes(b"checkpoint")
    return source_root, python, checkpoint


def _write_test_midi(path: Path) -> None:
    midi = pretty_midi.PrettyMIDI()
    instrument = pretty_midi.Instrument(program=0)
    instrument.notes.append(pretty_midi.Note(velocity=91, pitch=64, start=0.1, end=0.6))
    midi.instruments.append(instrument)
    midi.write(str(path))


def test_tsumugi_requires_explicit_external_runtime(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TSUMUGI_ROOT", raising=False)
    monkeypatch.delenv("TSUMUGI_PYTHON", raising=False)
    monkeypatch.delenv("TSUMUGI_CHECKPOINT", raising=False)

    engine = TsumugiEngine()

    with pytest.raises(RuntimeError, match="TSUMUGI_PYTHON"):
        engine.transcribe(b"RIFF-test", fmt="wav")


def test_tsumugi_invokes_pinned_cli_and_normalizes_midi(tmp_path: Path) -> None:
    source_root, python, checkpoint = _runtime_paths(tmp_path)
    calls: list[tuple[list[str], dict[str, object]]] = []

    def runner(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append((command, kwargs))
        output_path = Path(command[command.index("--output-midi") + 1])
        _write_test_midi(output_path)
        return subprocess.CompletedProcess(command, 0, stdout="ok", stderr="")

    engine = TsumugiEngine(
        source_root=source_root,
        python_executable=python,
        checkpoint=checkpoint,
        device="cpu",
        timeout_seconds=42,
        runner=runner,
    )
    result = engine.transcribe(b"RIFF-test", fmt="wav")

    assert len(calls) == 1
    command, kwargs = calls[0]
    assert command[:3] == [str(python), "-m", TsumugiEngine.MODULE]
    assert command[command.index("--checkpoint") + 1] == str(checkpoint)
    assert command[command.index("--device") + 1] == "cpu"
    assert "--disable-tqdm" in command
    assert kwargs == {
        "check": False,
        "capture_output": True,
        "text": True,
        "timeout": 42,
        "cwd": str(source_root),
    }
    assert result.midi.startswith(b"MThd")
    assert result.wav == b""
    assert result.num_notes == 1
    assert result.notes == [{"pitch": 64, "start": 0.1, "end": 0.6, "velocity": 91}]
    assert result.provenance.engine == "tsumugi"
    assert result.provenance.library_version == TsumugiEngine.SOURCE_COMMIT
    assert result.provenance.parameters["checkpoint"] == checkpoint.name


def test_tsumugi_verifies_configured_checkpoint_hash(tmp_path: Path) -> None:
    source_root, python, checkpoint = _runtime_paths(tmp_path)
    wrong_digest = hashlib.sha256(b"different").hexdigest()
    engine = TsumugiEngine(
        source_root=source_root,
        python_executable=python,
        checkpoint=checkpoint,
        checkpoint_sha256=wrong_digest,
    )

    with pytest.raises(RuntimeError, match="checkpoint SHA256 mismatch"):
        engine.transcribe(b"RIFF-test", fmt="wav")


def test_tsumugi_subprocess_failure_never_falls_back(tmp_path: Path) -> None:
    source_root, python, checkpoint = _runtime_paths(tmp_path)

    def runner(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(command, 7, stdout="", stderr="model failed")

    engine = TsumugiEngine(
        source_root=source_root,
        python_executable=python,
        checkpoint=checkpoint,
        runner=runner,
    )

    with pytest.raises(RuntimeError, match="exit code 7: model failed"):
        engine.transcribe(b"RIFF-test", fmt="wav")


def test_registry_exposes_tsumugi_only_as_explicit_engine(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TRANSCRIPTION_ENGINE", "basic_pitch")

    explicit = get_transcription_engine(name="tsumugi")
    auto = get_transcription_engine(profile="auto")

    assert explicit.__class__.__name__ == "TsumugiEngine"
    assert auto.__class__.__name__ == "BasicPitchEngine"