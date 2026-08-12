"""Audio-native key and chord analysis.

All functions operate on decoded audio (np.ndarray, sr).
Results carry provenance and are suitable for fusion with symbolic analysis.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np

_KS_MAJOR = np.array(
    [
        6.35,
        2.23,
        3.48,
        2.33,
        4.38,
        4.09,
        2.52,
        5.19,
        2.39,
        3.66,
        2.29,
        2.88,
    ],
    dtype=np.float64,
)
_KS_MINOR = np.array(
    [
        6.33,
        2.68,
        3.52,
        5.38,
        2.60,
        3.53,
        2.54,
        4.75,
        3.98,
        2.69,
        3.34,
        3.17,
    ],
    dtype=np.float64,
)
_NOTES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

_CHORD_TEMPLATES: dict[str, np.ndarray] = {}
for _root_idx in range(12):
    _base = np.zeros(12, dtype=np.float64)
    _base[_root_idx] = 1.0
    _base[(_root_idx + 4) % 12] = 1.0
    _base[(_root_idx + 7) % 12] = 1.0
    _CHORD_TEMPLATES[f"{_NOTES[_root_idx]}:maj"] = _base
    _base_min = np.zeros(12, dtype=np.float64)
    _base_min[_root_idx] = 1.0
    _base_min[(_root_idx + 3) % 12] = 1.0
    _base_min[(_root_idx + 7) % 12] = 1.0
    _CHORD_TEMPLATES[f"{_NOTES[_root_idx]}:min"] = _base_min

_N_TEMPLATES = len(_CHORD_TEMPLATES)


@dataclass(frozen=True)
class AudioKeyResult:
    tonic: str
    mode: str
    confidence: float
    source: str = "librosa_krumhansl"
    version: str = field(default_factory=lambda: _librosa_version())

    def to_dict(self) -> dict[str, Any]:
        return {
            "tonic": self.tonic,
            "mode": self.mode,
            "confidence": round(self.confidence, 3),
            "source": self.source,
            "version": self.version,
        }


@dataclass(frozen=True)
class AudioChordFrame:
    start_seconds: float
    end_seconds: float
    root: str
    quality: str
    confidence: float
    source: str = "librosa_chroma_template"


def detect_key(audio: np.ndarray, sr: float) -> AudioKeyResult | None:
    """Detect key from audio using librosa chroma + Krumhansl-Schmuckler profiles."""
    try:
        import librosa

        y_harm = librosa.effects.harmonic(audio.astype(np.float32))
        chroma = librosa.feature.chroma_cqt(y=y_harm, sr=float(sr))
        chroma_mean = np.mean(chroma, axis=1)
        if chroma_mean.sum() > 0:
            chroma_mean = chroma_mean / chroma_mean.max()

        best_corr = -1.0
        best_tonic = "C"
        best_mode = "major"
        for shift in range(12):
            rolled = np.roll(chroma_mean, shift)
            corr_major = float(np.dot(rolled, _KS_MAJOR))
            corr_minor = float(np.dot(rolled, _KS_MINOR))
            if corr_major > best_corr:
                best_corr = corr_major
                best_tonic = _NOTES[shift]
                best_mode = "major"
            if corr_minor > best_corr:
                best_corr = corr_minor
                best_tonic = _NOTES[shift]
                best_mode = "minor"

        max_possible = float(np.dot(_KS_MAJOR, _KS_MAJOR))
        confidence = best_corr / max_possible if max_possible > 0 else 0.0
        return AudioKeyResult(
            tonic=best_tonic,
            mode=best_mode,
            confidence=round(min(max(confidence, 0.0), 1.0), 3),
        )
    except Exception:
        return None


def estimate_chords(
    audio: np.ndarray,
    sr: float,
    hop_length: int = 512,
) -> list[AudioChordFrame]:
    """Estimate chord labels over time using beat-synchronous chroma + template matching."""
    import librosa

    y_harm = librosa.effects.harmonic(audio.astype(np.float32))
    chroma = librosa.feature.chroma_cqt(y=y_harm, sr=float(sr), hop_length=hop_length)
    chroma = chroma / (chroma.max(axis=0, keepdims=True) + 1e-10)

    tempo, beat_frames = librosa.beat.beat_track(
        y=audio.astype(np.float32),
        sr=float(sr),
        hop_length=hop_length,
    )
    if beat_frames is None or len(beat_frames) == 0:
        beat_frames = np.arange(0, chroma.shape[1], 8)
    beat_frames = np.unique(np.clip(beat_frames, 0, chroma.shape[1] - 1))
    times = librosa.frames_to_time(beat_frames, sr=sr, hop_length=hop_length)

    frames: list[AudioChordFrame] = []
    for i in range(len(times) - 1):
        start = times[i]
        end = times[i + 1]
        f_start = int(beat_frames[i])
        f_end = int(beat_frames[i + 1])
        segment = np.mean(chroma[:, f_start:f_end], axis=1)
        if segment.sum() == 0:
            continue
        segment = segment / segment.max()

        best_label = ""
        best_corr = -1.0
        for label, template in _CHORD_TEMPLATES.items():
            corr = float(np.dot(segment, template))
            if corr > best_corr:
                best_corr = corr
                best_label = label
        if best_label and best_corr > 0.3:
            root, quality = best_label.split(":", 1)
            frames.append(
                AudioChordFrame(
                    start_seconds=start,
                    end_seconds=end,
                    root=root,
                    quality=quality,
                    confidence=round(best_corr / 3.0, 3),
                )
            )
    return _merge_adjacent(frames)


def _merge_adjacent(frames: list[AudioChordFrame]) -> list[AudioChordFrame]:
    if not frames:
        return []
    merged = [frames[0]]
    for f in frames[1:]:
        prev = merged[-1]
        if f.root == prev.root and f.quality == prev.quality:
            merged[-1] = AudioChordFrame(
                start_seconds=prev.start_seconds,
                end_seconds=f.end_seconds,
                root=prev.root,
                quality=prev.quality,
                confidence=round((prev.confidence + f.confidence) / 2, 3),
            )
        else:
            merged.append(f)
    return merged


def _librosa_version() -> str:
    try:
        import librosa

        return librosa.__version__
    except Exception:
        return "unknown"
