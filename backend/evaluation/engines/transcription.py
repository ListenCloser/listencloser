"""Transcription engine adapters for OSS evaluation.

Adapters for:
- Basic Pitch (existing baseline)
- Transkun (qiuqiangkong/transkun)
- Piano Transcription (qiuqiangkong/piano_transcription)
"""

from __future__ import annotations

import logging
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from evaluation.engines import EngineInfo, EngineAdapter, EngineCategory

logger = logging.getLogger("eval.engines.transcription")


# ============================================================
# Basic Pitch (existing baseline - already in production)
# ============================================================

@dataclass
class BasicPitchAdapter(EngineAdapter):
    engine_info = EngineInfo(
        name="basic_pitch",
        category="transcription",
        repo_url="https://github.com/spotify/basic-pitch",
        license="MIT",
        install_cmd="pip install basic-pitch",
        model_size_mb=30,
        requires_gpu=False,
        notes="Spotify's onset/frame CNN. Current production baseline.",
    )

    def __init__(self, onset_threshold: float = 0.5, frame_threshold: float = 0.3, **kwargs):
        self._onset = onset_threshold
        self._frame = frame_threshold
        self._model = None

    def is_available(self) -> bool:
        try:
            from basic_pitch.inference import predict  # noqa: F401
            return True
        except Exception:
            return False

    def prepare(self) -> None:
        pass  # Basic Pitch loads model lazily

    def transcribe(self, audio_bytes: bytes, sample_rate: int = 44100, **kwargs) -> dict[str, Any]:
        import io
        import tempfile
        from basic_pitch.inference import predict

        # Write audio to temp file (Basic Pitch needs file path)
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            f.write(audio_bytes)
            temp_path = f.name

        try:
            model_output, midi_data, note_events = predict(
                temp_path,
                onset_threshold=self._onset,
                frame_threshold=self._frame,
            )

            # Extract notes from MIDI data
            notes = []
            for instrument in midi_data.instruments:
                for note in instrument.notes:
                    notes.append({
                        "pitch": note.pitch,
                        "start": note.start,
                        "end": note.end,
                        "velocity": note.velocity,
                    })

            # Get actual MIDI bytes (not fluidsynth audio)
            midi_buf = io.BytesIO()
            midi_data.write(midi_buf)
            midi_bytes = midi_buf.getvalue()

            return {
                "midi": midi_bytes,
                "notes": notes,
                "num_notes": len(notes),
                "note_events": note_events,
                "cleanup_report": {},
            }
        finally:
            try:
                os.unlink(temp_path)
            except Exception:
                pass

    def estimate_beats(self, audio_bytes: bytes, **kwargs) -> dict[str, Any]:
        raise NotImplementedError("BasicPitchAdapter does not support beat tracking")

    def analyze_harmony(self, midi_bytes: bytes, **kwargs) -> dict[str, Any]:
        raise NotImplementedError("BasicPitchAdapter does not support harmony")

    def analyze_structure(self, audio_bytes: bytes, **kwargs) -> dict[str, Any]:
        raise NotImplementedError("BasicPitchAdapter does not support structure")


# ============================================================
# Transkun
# ============================================================

@dataclass
class TranskunAdapter(EngineAdapter):
    engine_info = EngineInfo(
        name="transkun",
        category="transcription",
        repo_url="https://github.com/qiuqiangkong/transkun",
        license="MIT",
        install_cmd="pip install transkun",
        model_size_mb=150,  # Estimated
        requires_gpu=True,
        notes="Transformer-based piano transcription. Uses EfficientNet backbone + Transformer decoder.",
    )

    def __init__(self, device: str = "cpu", **kwargs):
        self._device = device
        self._model = None
        self._transcriber = None

    def is_available(self) -> bool:
        try:
            import transkun  # noqa: F401
            import torch  # noqa: F401
            return True
        except Exception:
            return False

    def prepare(self) -> None:
        if self._transcriber is not None:
            return

        try:
            from transkun import PianoTranscription
            self._transcriber = PianoTranscription(device=self._device)
        except Exception as e:
            logger.warning("Transkun prepare failed: %s", e)
            self._transcriber = None

    def transcribe(self, audio_bytes: bytes, sample_rate: int = 44100, **kwargs) -> dict[str, Any]:
        import io
        import soundfile as sf
        import tempfile

        if self._transcriber is None:
            self.prepare()
        if self._transcriber is None:
            raise RuntimeError("Transkun not available")

        # Write audio to temp file
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            f.write(audio_bytes)
            temp_path = f.name

        try:
            # Transkun expects file path
            midi_data = self._transcriber.transcribe(temp_path)

            notes = []
            for instrument in midi_data.instruments:
                for note in instrument.notes:
                    notes.append({
                        "pitch": note.pitch,
                        "start": note.start,
                        "end": note.end,
                        "velocity": note.velocity,
                    })

            # Get actual MIDI bytes (not fluidsynth audio)
            midi_buf = io.BytesIO()
            midi_data.write(midi_buf)
            midi_bytes = midi_buf.getvalue()

            return {
                "midi": midi_bytes,
                "notes": notes,
                "num_notes": len(notes),
            }
        finally:
            try:
                os.unlink(temp_path)
            except Exception:
                pass

    def estimate_beats(self, audio_bytes: bytes, **kwargs) -> dict[str, Any]:
        raise NotImplementedError

    def analyze_harmony(self, midi_bytes: bytes, **kwargs) -> dict[str, Any]:
        raise NotImplementedError

    def analyze_structure(self, audio_bytes: bytes, **kwargs) -> dict[str, Any]:
        raise NotImplementedError


# ============================================================
# Piano Transcription (qiuqiangkong/piano_transcription)
# ============================================================

@dataclass
class PianoTranscriptionAdapter(EngineAdapter):
    engine_info = EngineInfo(
        name="piano_transcription",
        category="transcription",
        repo_url="https://github.com/qiuqiangkong/piano_transcription",
        license="MIT",
        install_cmd="pip install piano_transcription",
        model_size_mb=200,
        requires_gpu=True,
        notes="CNN-Transformer piano transcription from qiuqiangkong. High-quality piano specialist.",
    )

    def __init__(self, device: str = "cpu", **kwargs):
        self._device = device
        self._model = None

    def is_available(self) -> bool:
        try:
            import piano_transcription  # noqa: F401
            import torch  # noqa: F401
            return True
        except Exception:
            return False

    def prepare(self) -> None:
        if self._model is not None:
            return
        try:
            from piano_transcription.inference import load_model
            self._model = load_model(device=self._device)
        except Exception as e:
            logger.warning("Piano Transcription prepare failed: %s", e)
            self._model = None

    def transcribe(self, audio_bytes: bytes, sample_rate: int = 44100, **kwargs) -> dict[str, Any]:
        import io
        import soundfile as sf
        import tempfile

        if self._model is None:
            self.prepare()
        if self._model is None:
            raise RuntimeError("Piano Transcription model not available")

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            f.write(audio_bytes)
            temp_path = f.name

        try:
            from piano_transcription.inference import transcribe_audio
            midi_data = transcribe_audio(temp_path, self._model)

            notes = []
            for instrument in midi_data.instruments:
                for note in instrument.notes:
                    notes.append({
                        "pitch": note.pitch,
                        "start": note.start,
                        "end": note.end,
                        "velocity": note.velocity,
                    })

            # Get actual MIDI bytes (not fluidsynth audio)
            midi_buf = io.BytesIO()
            midi_data.write(midi_buf)
            midi_bytes = midi_buf.getvalue()

            return {
                "midi": midi_bytes,
                "notes": notes,
                "num_notes": len(notes),
            }
        finally:
            try:
                os.unlink(temp_path)
            except Exception:
                pass

    def estimate_beats(self, audio_bytes: bytes, **kwargs) -> dict[str, Any]:
        raise NotImplementedError

    def analyze_harmony(self, midi_bytes: bytes, **kwargs) -> dict[str, Any]:
        raise NotImplementedError

    def analyze_structure(self, audio_bytes: bytes, **kwargs) -> dict[str, Any]:
        raise NotImplementedError


# ============================================================
# Registry
# ============================================================

TRANSCRIPTION_ADAPTERS = {
    "basic_pitch": BasicPitchAdapter,
    "transkun": TranskunAdapter,
    "piano_transcription": PianoTranscriptionAdapter,
}


def get_transcription_adapter(name: str, **kwargs) -> EngineAdapter:
    if name not in TRANSCRIPTION_ADAPTERS:
        raise ValueError(f"Unknown transcription adapter: {name}. Available: {list(TRANSCRIPTION_ADAPTERS)}")
    return TRANSCRIPTION_ADAPTERS[name](**kwargs)


def list_transcription_adapters() -> list[str]:
    return list(TRANSCRIPTION_ADAPTERS.keys())