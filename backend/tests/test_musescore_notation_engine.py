import json
import pathlib
import subprocess

import pytest
from engines.notation.musescore_engine import MuseScoreNotationEngine
from engines.registry import get_notation_engine

MIDI_BYTES = b"MThd" + b"\x00" * 32
MUSICXML_BYTES = b'<?xml version="1.0"?><score-partwise version="4.0"></score-partwise>'
NOTATION_MIDI_BYTES = b"MThd" + b"\x01" * 32


def _fake_musescore_run(args, **kwargs):
    assert args[1:3] == ["-platform", "offscreen"]
    command_args = args[3:]

    if command_args == ["--version"]:
        return subprocess.CompletedProcess(args, 0, stdout="MuseScore Studio 4.7.5\n", stderr="")

    assert command_args[0] == "--job"
    job_path = pathlib.Path(command_args[1])
    job = json.loads(job_path.read_text(encoding="utf-8"))
    assert len(job) == 1
    assert pathlib.Path(job[0]["in"]).read_bytes() == MIDI_BYTES

    output_xml, output_midi = (pathlib.Path(path) for path in job[0]["out"])
    output_xml.write_bytes(MUSICXML_BYTES)
    output_midi.write_bytes(NOTATION_MIDI_BYTES)
    return subprocess.CompletedProcess(args, 0, stdout="", stderr="")


def test_musescore_adapter_exports_normalized_midi_and_musicxml(monkeypatch):
    engine = MuseScoreNotationEngine(executable="/opt/musescore/MuseScore-Studio.AppImage")
    monkeypatch.setattr(engine, "_run", _fake_musescore_run)

    result = engine.convert(
        MIDI_BYTES,
        [0.0, 0.5, 1.0, 1.5],
        downbeats=[0.0],
        beat_positions=[1, 2, 3, 4],
        adaptive=True,
        piano_grand_staff=True,
    )

    assert result.musicxml == MUSICXML_BYTES
    assert result.notation_midi == NOTATION_MIDI_BYTES
    assert result.provenance.engine == "musescore"
    assert result.provenance.library_version == "MuseScore Studio 4.7.5"
    assert result.provenance.parameters["beat_grid_consumed"] is False
    assert result.quantization_report["beat_grid_available"] is True
    assert result.quantization_report["beat_grid_consumed"] is False
    assert result.quantization_report["beat_count"] == 4
    assert result.quantization_report["downbeat_count"] == 1
    assert result.quantization_report["adaptive_requested"] is True
    assert result.quantization_report["piano_grand_staff_requested"] is True


def test_musescore_adapter_isolated_headless_environment():
    root = pathlib.Path("/tmp/example")
    env = MuseScoreNotationEngine._isolated_environment(root)

    assert env["QT_QPA_PLATFORM"] == "offscreen"
    assert env["SKIP_LIBJACK"] == "1"
    assert env["XDG_CONFIG_HOME"] == "/tmp/example/config"
    assert env["XDG_DATA_HOME"] == "/tmp/example/data"
    assert env["XDG_CACHE_HOME"] == "/tmp/example/cache"


def test_musescore_adapter_fails_closed_when_conversion_fails(monkeypatch):
    engine = MuseScoreNotationEngine(executable="/opt/musescore/MuseScore-Studio.AppImage")

    def fail_run(args, **kwargs):
        assert args[1:3] == ["-platform", "offscreen"]
        if args[3:] == ["--version"]:
            return subprocess.CompletedProcess(
                args,
                0,
                stdout="MuseScore Studio 4.7.5\n",
                stderr="",
            )
        return subprocess.CompletedProcess(args, 2, stdout="", stderr="import failed")

    monkeypatch.setattr(engine, "_run", fail_run)

    with pytest.raises(RuntimeError, match="MuseScore conversion failed with exit 2"):
        engine.convert(MIDI_BYTES, [0.0, 0.5])


def test_musescore_adapter_rejects_non_midi_input():
    engine = MuseScoreNotationEngine(executable="/opt/musescore/MuseScore-Studio.AppImage")

    with pytest.raises(ValueError, match="must be a MIDI file"):
        engine.convert(b"not midi", [])


def test_musescore_is_opt_in_registry_candidate(monkeypatch):
    monkeypatch.delenv("NOTATION_ENGINE", raising=False)

    assert get_notation_engine().provenance.engine == "music21"
    candidate = get_notation_engine("musescore")
    assert isinstance(candidate, MuseScoreNotationEngine)
