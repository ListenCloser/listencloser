import wave
from types import SimpleNamespace

import pytest

import audio_processing


def _write_test_wav(path, *, seconds: float = 0.1, sample_rate: int = 8000) -> None:
    frame_count = int(seconds * sample_rate)
    with wave.open(str(path), "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(b"\x00\x00" * frame_count)


def test_decode_audio_to_wav_hard_caps_ffmpeg_duration(monkeypatch):
    commands: list[list[str]] = []

    def fake_run(command, **_kwargs):
        commands.append(command)
        _write_test_wav(command[-1])
        return SimpleNamespace(returncode=0, stderr=b"")

    monkeypatch.setenv("MAX_DECODED_AUDIO_SECONDS", "60")
    monkeypatch.setattr(audio_processing.subprocess, "run", fake_run)

    decoded = audio_processing.decode_audio_to_wav(b"compressed-audio", fmt="mp3")

    assert decoded.startswith(b"RIFF")
    command = commands[0]
    duration_flag = command.index("-t")
    assert command[duration_flag + 1] == "61.0"


def test_decode_audio_to_wav_rejects_source_over_duration_limit(monkeypatch):
    def fake_run(command, **_kwargs):
        _write_test_wav(command[-1])
        return SimpleNamespace(returncode=0, stderr=b"")

    monkeypatch.setenv("MAX_DECODED_AUDIO_SECONDS", "60")
    monkeypatch.setattr(audio_processing.subprocess, "run", fake_run)
    monkeypatch.setattr(audio_processing, "_wav_duration_seconds", lambda _path: 60.5)

    with pytest.raises(ValueError, match="maximum duration of 60 seconds"):
        audio_processing.decode_audio_to_wav(b"compressed-audio", fmt="mp3")


def test_decode_audio_to_wav_accepts_audio_at_duration_limit(monkeypatch):
    def fake_run(command, **_kwargs):
        _write_test_wav(command[-1])
        return SimpleNamespace(returncode=0, stderr=b"")

    monkeypatch.setenv("MAX_DECODED_AUDIO_SECONDS", "60")
    monkeypatch.setattr(audio_processing.subprocess, "run", fake_run)
    monkeypatch.setattr(audio_processing, "_wav_duration_seconds", lambda _path: 60.0)

    decoded = audio_processing.decode_audio_to_wav(b"compressed-audio", fmt="mp3")

    assert decoded.startswith(b"RIFF")
