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
        requires_gpu=False,
        python_version=">=3.9",
        notes="Transformer-based piano transcription. Uses EfficientNet backbone + Transformer decoder. Pretrained model included.",
    )

    def __init__(self, device: str = "cpu", **kwargs):
        self._device = device
        self._model = None

    def is_available(self) -> bool:
        try:
            import transkun  # noqa: F401
            import torch  # noqa: F401
            import moduleconf  # noqa: F401
            return True
        except Exception:
            return False

    def prepare(self) -> None:
        if self._model is not None:
            return

        try:
            import torch
            import moduleconf
            from transkun.transcribe import readAudio, writeMidi

            # Load config and weights from transkun's pretrained directory
            import pkg_resources
            default_weight = pkg_resources.resource_filename("transkun.transcribe", "pretrained/2.0.pt")
            default_conf = pkg_resources.resource_filename("transkun.transcribe", "pretrained/2.0.conf")

            conf_manager = moduleconf.parseFromFile(default_conf)
            ModelClass = conf_manager["Model"].module.TransKun
            conf = conf_manager["Model"].config

            checkpoint = torch.load(default_weight, map_location=self._device)
            self._model = ModelClass(conf=conf).to(self._device)

            if "best_state_dict" in checkpoint:
                self._model.load_state_dict(checkpoint["best_state_dict"], strict=False)
            else:
                self._model.load_state_dict(checkpoint["state_dict"], strict=False)

            self._model.eval()
        except Exception as e:
            logger.warning("Transkun prepare failed: %s", e)
            self._model = None

    def transcribe(self, audio_bytes: bytes, sample_rate: int = 44100, **kwargs) -> dict[str, Any]:
        import io
        import os
        import tempfile

        if self._model is None:
            self.prepare()
        if self._model is None:
            raise RuntimeError("Transkun not available")

        from transkun.transcribe import readAudio, writeMidi
        import torch

        # Detect audio format from content bytes
        fmt = "wav"
        if audio_bytes[:4] == b"RIFF":
            fmt = "wav"
        elif audio_bytes[:4] == b"OggS":
            fmt = "ogg"
        elif audio_bytes[:2] == b"\xff\xfb":
            fmt = "mp3"
        elif len(audio_bytes) >= 12 and audio_bytes[4:8] == b"ftyp":
            fmt = "m4a"

        # Write audio to temp file for Transkun's readAudio
        with tempfile.NamedTemporaryFile(suffix=f".{fmt}", delete=False) as f:
            f.write(audio_bytes)
            temp_audio = f.name

        # Write MIDI to temp file
        temp_midi = temp_audio.rsplit(".", 1)[0] + ".mid"

        try:
            fs, audio = readAudio(temp_audio)

            torch.set_grad_enabled(False)

            # Resample if needed
            if fs != self._model.fs:
                try:
                    import soxr
                    audio = soxr.resample(audio, fs, self._model.fs)
                except ImportError:
                    logger.warning("soxr not installed, skipping resampling")

            x = torch.from_numpy(audio).to(self._device)

            notes_est = self._model.transcribe(x, stepInSecond=kwargs.get("segment_hop_size"), segmentSizeInSecond=kwargs.get("segment_size"), discardSecondHalf=False)

            writeMidi(notes_est).write(temp_midi)

            import pretty_midi
            midi_data = pretty_midi.PrettyMIDI(temp_midi)

            notes = []
            for instrument in midi_data.instruments:
                for note in instrument.notes:
                    notes.append({
                        "pitch": note.pitch,
                        "start": note.start,
                        "end": note.end,
                        "velocity": note.velocity,
                    })

            midi_bytes = Path(temp_midi).read_bytes()

            return {
                "midi": midi_bytes,
                "notes": notes,
                "num_notes": len(notes),
            }
        finally:
            for p in [temp_audio, temp_midi]:
                try:
                    os.unlink(p)
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
        install_cmd="pip install piano-transcription-inference",
        model_size_mb=200,
        requires_gpu=False,
        python_version=">=3.9",
        notes="CNN-Transformer piano transcription by Qiuqiang Kong. Checkpoint auto-downloaded on first use.",
    )

    def __init__(self, device: str = "cpu", **kwargs):
        self._device = device
        self._model = None

    def is_available(self) -> bool:
        try:
            from piano_transcription_inference import PianoTranscription  # noqa: F401
            return True
        except Exception:
            return False

    def prepare(self) -> None:
        if self._model is not None:
            return
        try:
            from piano_transcription_inference import PianoTranscription
            self._model = PianoTranscription(device=self._device)
        except Exception as e:
            logger.warning("Piano Transcription prepare failed: %s", e)
            self._model = None

    def transcribe(self, audio_bytes: bytes, sample_rate: int = 44100, **kwargs) -> dict[str, Any]:
        import io
        import tempfile
        import numpy as np

        if self._model is None:
            self.prepare()
        if self._model is None:
            raise RuntimeError("Piano Transcription model not available")

        # Detect audio format from content bytes and write to temp file
        # (soundfile/libsndfile doesn't support m4a; use pydub for format detection+conversion)
        import librosa
        import soundfile as sf

        # Detect format from magic bytes
        fmt = "wav"
        if audio_bytes[:4] == b"RIFF":
            fmt = "wav"
        elif audio_bytes[:4] == b"OggS":
            fmt = "ogg"
        elif audio_bytes[:2] == b"\xff\xfb":
            fmt = "mp3"
        elif len(audio_bytes) >= 12 and audio_bytes[4:8] == b"ftyp":
            fmt = "m4a"

        # soundfile can't read m4a/mp3 directly; use librosa with audioread fallback
        if fmt in ("wav", "ogg", "flac"):
            audio, sr = librosa.load(io.BytesIO(audio_bytes), sr=sample_rate, mono=True)
        else:
            # For m4a/mp3: write to temp file and let librosa use audioread backend
            with tempfile.NamedTemporaryFile(suffix=f".{fmt}", delete=False) as tmp:
                tmp.write(audio_bytes)
                tmp_path = tmp.name
            try:
                audio, sr = librosa.load(tmp_path, sr=sample_rate, mono=True)
            finally:
                import os
                os.unlink(tmp_path)

        with tempfile.NamedTemporaryFile(suffix=".mid", delete=False) as f:
            temp_midi = f.name

        try:
            self._model.transcribe(audio, temp_midi)

            import pretty_midi
            midi_data = pretty_midi.PrettyMIDI(temp_midi)
            midi_bytes = Path(temp_midi).read_bytes()

            notes = []
            for instrument in midi_data.instruments:
                for note in instrument.notes:
                    notes.append({
                        "pitch": note.pitch,
                        "start": note.start,
                        "end": note.end,
                        "velocity": note.velocity,
                    })

            return {
                "midi": midi_bytes,
                "notes": notes,
                "num_notes": len(notes),
            }
        finally:
            try:
                os.unlink(temp_midi)
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