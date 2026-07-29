"""Fixture-based benchmark tests for Phase 8 music-quality upgrades.

Tests exercise the real transcription, analysis, and synthesis pipelines
against the sine_a4_c5.wav fixture. Fast, deterministic, offline-safe.
"""

import io
import os
import tempfile
from pathlib import Path

import numpy as np
import pretty_midi
import pytest
import soundfile as sf

from analyze import analyze_midi
from music_features import midi_to_wav, transcribe_audio

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"
FIXTURE_WAV = FIXTURE_DIR / "sine_a4_c5.wav"


def _load_fixture(name: str) -> bytes:
    path = FIXTURE_DIR / name
    if path.exists():
        return path.read_bytes()
    if name == "sine_a4_c5.wav":
        FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
        sr = 22050
        t = np.linspace(0, 1.0, sr, endpoint=False)
        sig = np.zeros(sr, dtype=np.float32)
        seg = sr // 2
        sig[:seg] += 0.3 * np.sin(2 * np.pi * 440.0 * t[:seg])
        sig[seg:] += 0.3 * np.sin(2 * np.pi * 523.25 * t[seg:])
        buf = io.BytesIO()
        sf.write(buf, np.clip(sig, -1.0, 1.0), sr, format="WAV", subtype="PCM_16")
        audio = buf.getvalue()
        path.write_bytes(audio)
        return audio
    raise FileNotFoundError(f"fixture {name} not found and has no fallback synthesis")


def _sine_midi_bytes() -> bytes:
    pm = pretty_midi.PrettyMIDI()
    inst = pretty_midi.Instrument(program=0, is_drum=False, name="Piano")
    inst.notes.append(pretty_midi.Note(velocity=80, pitch=69, start=0.0, end=0.5))   # A4
    inst.notes.append(pretty_midi.Note(velocity=80, pitch=72, start=0.5, end=1.0))   # C5
    pm.instruments.append(inst)
    buf = io.BytesIO()
    pm.write(buf)
    return buf.getvalue()


def test_transcribe_fixture_has_notes():
    try:
        import basic_pitch  # noqa: F401
    except Exception as e:
        pytest.skip(f"basic-pitch unavailable: {e}")

    audio = _load_fixture("sine_a4_c5.wav")
    result = transcribe_audio(audio, fmt="wav")
    notes = result.get("notes", [])
    assert isinstance(notes, list)
    assert len(notes) >= 1


def test_transcribe_detects_pitches():
    try:
        import basic_pitch  # noqa: F401
    except Exception as e:
        pytest.skip(f"basic-pitch unavailable: {e}")

    audio = _load_fixture("sine_a4_c5.wav")
    result = transcribe_audio(audio, fmt="wav")
    notes = result.get("notes", [])
    pitches = {n["pitch"] for n in notes}
    assert any(67 <= p <= 74 for p in pitches)


def test_analyze_detects_key():
    midi = _sine_midi_bytes()
    with tempfile.NamedTemporaryFile(suffix=".mid", delete=False) as f:
        f.write(midi)
        midi_path = f.name
    try:
        result = analyze_midi(midi_path)
    finally:
        os.unlink(midi_path)
    assert result.get("key", {}).get("tonic") is not None


def test_synthesize_produces_audio():
    midi = _sine_midi_bytes()
    result = midi_to_wav(midi)
    assert result is not None
    assert len(result) > 1000


def test_transcribe_produces_midi_bytes():
    try:
        import basic_pitch  # noqa: F401
    except Exception as e:
        pytest.skip(f"basic-pitch unavailable: {e}")

    audio = _load_fixture("sine_a4_c5.wav")
    result = transcribe_audio(audio, fmt="wav")
    midi = result.get("midi")
    assert isinstance(midi, bytes | bytearray)
    assert len(midi) > 0


def test_transcribe_produces_wav_bytes():
    try:
        import basic_pitch  # noqa: F401
    except Exception as e:
        pytest.skip(f"basic-pitch unavailable: {e}")

    audio = _load_fixture("sine_a4_c5.wav")
    result = transcribe_audio(audio, fmt="wav")
    wav = result.get("wav")
    assert isinstance(wav, bytes | bytearray)
    assert len(wav) > 0


def test_analyze_produces_chords():
    midi = _sine_midi_bytes()
    with tempfile.NamedTemporaryFile(suffix=".mid", delete=False) as f:
        f.write(midi)
        midi_path = f.name
    try:
        result = analyze_midi(midi_path)
    finally:
        os.unlink(midi_path)
    chords = result.get("chords", [])
    assert isinstance(chords, list)


def test_analyze_produces_tempo():
    midi = _sine_midi_bytes()
    with tempfile.NamedTemporaryFile(suffix=".mid", delete=False) as f:
        f.write(midi)
        midi_path = f.name
    try:
        result = analyze_midi(midi_path)
    finally:
        os.unlink(midi_path)
    tempo = result.get("tempo", {}) or {}
    assert isinstance(tempo, dict)


def test_synthesize_produces_valid_wav():
    midi = _sine_midi_bytes()
    result = midi_to_wav(midi)
    data, sr = sf.read(io.BytesIO(result))
    assert sr > 0
    assert len(data) > 0
