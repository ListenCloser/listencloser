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

        # librosa needs a file path for .m4a (uses audioread)
        with tempfile.NamedTemporaryFile(suffix=".m4a", delete=False) as f:
            f.write(audio_bytes)
            temp_path = f.name

        try:
            y, sr = librosa.load(temp_path, sr=sample_rate, mono=True)
            if sr != sample_rate:
                y = librosa.resample(y, orig_sr=sr, target_sr=sample_rate)
                sr = sample_rate

            onset_env = librosa.onset.onset_strength(y=y, sr=sr)
            tempo, beats = librosa.beat.beat_track(onset_envelope=onset_env, sr=sr)
            beats_time = librosa.frames_to_time(beats, sr=sr)

            # Downbeats (optional, librosa doesn't do this well)
            downbeats = None

            return {
                "bpm": float(tempo),
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
            import beat_this  # noqa: F401
            import torch  # noqa: F401
            return True
        except Exception:
            return False

    def prepare(self) -> None:
        if self._model is not None:
            return
        try:
            from beat_this import BeatThis
            self._model = BeatThis(device=self._device)
        except Exception as e:
            logger.warning("BeatThis prepare failed: %s", e)
            self._model = None

    def estimate_beats(self, audio_bytes: bytes, sample_rate: int = 44100, **kwargs) -> dict[str, Any]:
        import io
        import soundfile as sf
        import tempfile

        if self._model is None:
            self.prepare()
        if self._model is None:
            raise RuntimeError("BeatThis model not available")

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            f.write(audio_bytes)
            temp_path = f.name

        try:
            beats, downbeats = self._model.predict(temp_path)
            return {
                "bpm": 60.0 / (beats[1] - beats[0]) if len(beats) > 1 else 120.0,
                "beats": beats.tolist() if hasattr(beats, "tolist") else list(beats),
                "downbeats": downbeats.tolist() if downbeats is not None else None,
                "beat_positions": list(range(1, len(beats) + 1)),
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
        install_cmd="pip install beatnet",
        model_size_mb=80,
        requires_gpu=True,
        notes="TCN-based beat/downbeat tracker. Good for complex rhythms.",
    )

    def __init__(self, device: str = "cpu", **kwargs):
        self._device = device
        self._model = None

    def is_available(self) -> bool:
        try:
            import beatnet  # noqa: F401
            import torch  # noqa: F401
            return True
        except Exception:
            return False

    def prepare(self) -> None:
        if self._model is not None:
            return
        try:
            from beatnet import BeatNet
            self._model = BeatNet(device=self._device)
        except Exception as e:
            logger.warning("BeatNet prepare failed: %s", e)
            self._model = None

    def estimate_beats(self, audio_bytes: bytes, sample_rate: int = 44100, **kwargs) -> dict[str, Any]:
        import io
        import soundfile as sf
        import tempfile

        if self._model is None:
            self.prepare()
        if self._model is None:
            raise RuntimeError("BeatNet model not available")

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            f.write(audio_bytes)
            temp_path = f.name

        try:
            beats, downbeats = self._model.predict(temp_path)
            return {
                "bpm": 60.0 / (beats[1] - beats[0]) if len(beats) > 1 else 120.0,
                "beats": beats.tolist() if hasattr(beats, "tolist") else list(beats),
                "downbeats": downbeats.tolist() if downbeats is not None else None,
                "beat_positions": list(range(1, len(beats) + 1)),
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