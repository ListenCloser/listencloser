"""Beat tracking engine adapters for OSS evaluation.

Adapters for:
- Librosa (existing baseline)
- Beat This (inria-ml/beat_this)
- BeatNet (mzsd/beatnet)
"""

from __future__ import annotations

import logging
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from evaluation.engines import EngineInfo, EngineAdapter, EngineCategory

logger = logging.getLogger("eval.engines.beat_tracking")


# ============================================================
# Librosa (existing baseline - already in production)
# ============================================================

@dataclass
class LibrosaBeatAdapter(EngineAdapter):
    engine_info = EngineInfo(
        name="librosa",
        category="beat_tracking",
        repo_url="https://github.com/librosa/librosa",
        license="ISC",
        install_cmd="pip install librosa",
        model_size_mb=0,  # No ML model
        requires_gpu=False,
        notes="Spectral onset + dynamic programming. Current production baseline.",
    )

    def __init__(self, **kwargs):
        pass

    def is_available(self) -> bool:
        try:
            import librosa  # noqa: F401
            return True
        except Exception:
            return False

    def prepare(self) -> None:
        pass

    def estimate_beats(self, audio_bytes: bytes, sample_rate: int = 44100, **kwargs) -> dict[str, Any]:
        import librosa
        import tempfile
        import os

        # Detect audio format from magic bytes for correct temp file extension
        fmt = "wav"
        if audio_bytes[:4] == b"RIFF":
            fmt = "wav"
        elif audio_bytes[:4] == b"OggS":
            fmt = "ogg"
        elif audio_bytes[:2] == b"\xff\xfb":
            fmt = "mp3"
        elif len(audio_bytes) >= 12 and audio_bytes[4:8] == b"ftyp":
            fmt = "m4a"

        with tempfile.NamedTemporaryFile(suffix=f".{fmt}", delete=False) as f:
            f.write(audio_bytes)
            temp_path = f.name

        try:
            y, sr = librosa.load(temp_path, sr=sample_rate, mono=True)
            if sr != sample_rate:
                y = librosa.resample(y, orig_sr=sr, target_sr=sample_rate)
                sr = sample_rate

            onset_env = librosa.onset.onset_strength(y=y, sr=sr)
            tempo, beats = librosa.beat.beat_track(onset_envelope=onset_env, sr=sr)
            tempo_val = float(tempo.item()) if hasattr(tempo, 'item') else float(tempo)
            beats_time = librosa.frames_to_time(beats, sr=sr)

            # Downbeats (optional, librosa doesn't do this well)
            downbeats = None

            return {
                "bpm": tempo_val,
                "beats": beats_time.tolist(),
                "downbeats": downbeats,
                "beat_positions": list(range(1, len(beats_time) + 1)),
            }
        finally:
            try:
                os.unlink(temp_path)
            except Exception:
                pass

    def transcribe(self, audio_bytes: bytes, **kwargs) -> dict[str, Any]:
        raise NotImplementedError

    def analyze_harmony(self, midi_bytes: bytes, **kwargs) -> dict[str, Any]:
        raise NotImplementedError

    def analyze_structure(self, audio_bytes: bytes, **kwargs) -> dict[str, Any]:
        raise NotImplementedError


# ============================================================
# Beat This
# ============================================================

@dataclass
class BeatThisAdapter(EngineAdapter):
    engine_info = EngineInfo(
        name="beat_this",
        category="beat_tracking",
        repo_url="https://github.com/inria-ml/beat_this",
        license="MIT",
        install_cmd="pip install beat-this",
        model_size_mb=50,
        requires_gpu=True,
        notes="CNN-based beat/downbeat tracker from INRIA. State-of-the-art on GTZAN.",
    )

    def __init__(self, device: str = "cpu", **kwargs):
        self._device = device
        self._model = None

    def is_available(self) -> bool:
        try:
            from beat_this.inference import File2Beats  # noqa: F401
            return True
        except Exception:
            return False

    def prepare(self) -> None:
        if self._model is not None:
            return
        try:
            from beat_this.inference import File2Beats
            self._model = File2Beats(device=self._device)
        except Exception as e:
            logger.warning("BeatThis prepare failed: %s", e)
            self._model = None

    def estimate_beats(self, audio_bytes: bytes, sample_rate: int = 44100, **kwargs) -> dict[str, Any]:
        import numpy as np
        import tempfile

        if self._model is None:
            self.prepare()
        if self._model is None:
            raise RuntimeError("BeatThis model not available")

        # Detect audio format from magic bytes
        fmt = "wav"
        if audio_bytes[:4] == b"RIFF":
            fmt = "wav"
        elif audio_bytes[:4] == b"OggS":
            fmt = "ogg"
        elif audio_bytes[:2] == b"\xff\xfb":
            fmt = "mp3"
        elif len(audio_bytes) >= 12 and audio_bytes[4:8] == b"ftyp":
            fmt = "m4a"

        with tempfile.NamedTemporaryFile(suffix=f".{fmt}", delete=False) as f:
            f.write(audio_bytes)
            temp_path = f.name

        try:
            beats, downbeats = self._model(temp_path)

            beats_time = beats.tolist() if hasattr(beats, "tolist") else list(beats)
            downbeats_time = downbeats.tolist() if hasattr(downbeats, "tolist") else list(downbeats)

            bpm = 60.0 / (beats_time[1] - beats_time[0]) if len(beats_time) > 1 else 120.0

            return {
                "bpm": float(bpm),
                "beats": beats_time,
                "downbeats": downbeats_time if downbeats_time else None,
                "beat_positions": list(range(1, len(beats_time) + 1)),
            }
        finally:
            try:
                os.unlink(temp_path)
            except Exception:
                pass

    def transcribe(self, audio_bytes: bytes, **kwargs) -> dict[str, Any]:
        raise NotImplementedError

    def analyze_harmony(self, midi_bytes: bytes, **kwargs) -> dict[str, Any]:
        raise NotImplementedError

    def analyze_structure(self, audio_bytes: bytes, **kwargs) -> dict[str, Any]:
        raise NotImplementedError


# ============================================================
# BeatNet
# ============================================================

@dataclass
class BeatNetAdapter(EngineAdapter):
    engine_info = EngineInfo(
        name="beatnet",
        category="beat_tracking",
        repo_url="https://github.com/mzsd/BeatNet",
        license="MIT",
        install_cmd="pip install beatnet madmom",
        model_size_mb=80,
        requires_gpu=False,
        python_version=">=3.9",
        notes="TCN-based beat/downbeat tracker. Good for complex rhythms. Requires madmom (C extension, may need system compiler).",
    )

    def __init__(self, device: str = "cpu", **kwargs):
        self._device = device
        self._model = None

    def is_available(self) -> bool:
        try:
            from BeatNet import BeatNet  # noqa: F401
            return True
        except Exception:
            return False

    def prepare(self) -> None:
        if self._model is not None:
            return
        try:
            from BeatNet import BeatNet
            self._model = BeatNet(device=self._device)
        except Exception as e:
            logger.warning("BeatNet prepare failed: %s", e)
            self._model = None

    def estimate_beats(self, audio_bytes: bytes, sample_rate: int = 44100, **kwargs) -> dict[str, Any]:
        import os
        import tempfile

        if self._model is None:
            self.prepare()
        if self._model is None:
            raise RuntimeError("BeatNet model not available")

        # Detect audio format from magic bytes
        fmt = "wav"
        if audio_bytes[:4] == b"RIFF":
            fmt = "wav"
        elif audio_bytes[:4] == b"OggS":
            fmt = "ogg"
        elif audio_bytes[:2] == b"\xff\xfb":
            fmt = "mp3"
        elif len(audio_bytes) >= 12 and audio_bytes[4:8] == b"ftyp":
            fmt = "m4a"

        with tempfile.NamedTemporaryFile(suffix=f".{fmt}", delete=False) as f:
            f.write(audio_bytes)
            temp_path = f.name

        try:
            # BeatNet.predict returns (beats_times, downbeats_times, beat_conf, downbeat_conf)
            result = self._model.predict(temp_path)
            if len(result) == 4:
                beats, downbeats, beat_conf, downbeat_conf = result
            else:
                beats, downbeats = result
                beat_conf = downbeat_conf = None

            beats_time = beats.tolist() if hasattr(beats, "tolist") else list(beats)
            downbeats_time = downbeats.tolist() if hasattr(downbeats, "tolist") else list(downbeats)

            bpm = 60.0 / (beats_time[1] - beats_time[0]) if len(beats_time) > 1 else 120.0

            return {
                "bpm": float(bpm),
                "beats": beats_time,
                "downbeats": downbeats_time if downbeats_time else None,
                "beat_positions": list(range(1, len(beats_time) + 1)),
            }
        finally:
            try:
                os.unlink(temp_path)
            except Exception:
                pass

    def transcribe(self, audio_bytes: bytes, **kwargs) -> dict[str, Any]:
        raise NotImplementedError

    def analyze_harmony(self, midi_bytes: bytes, **kwargs) -> dict[str, Any]:
        raise NotImplementedError

    def analyze_structure(self, audio_bytes: bytes, **kwargs) -> dict[str, Any]:
        raise NotImplementedError


# ============================================================
# Registry
# ============================================================

BEAT_TRACKING_ADAPTERS = {
    "librosa": LibrosaBeatAdapter,
    "beat_this": BeatThisAdapter,
    "beatnet": BeatNetAdapter,
}


def get_beat_tracking_adapter(name: str, **kwargs) -> EngineAdapter:
    if name not in BEAT_TRACKING_ADAPTERS:
        raise ValueError(f"Unknown beat tracking adapter: {name}. Available: {list(BEAT_TRACKING_ADAPTERS)}")
    return BEAT_TRACKING_ADAPTERS[name](**kwargs)


def list_beat_tracking_adapters() -> list[str]:
    return list(BEAT_TRACKING_ADAPTERS.keys())