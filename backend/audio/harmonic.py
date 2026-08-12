"""Audio-native key and chord analysis using librosa chroma.

Key detection uses normalized Krumhansl-Schmuckler correlation.
Chord estimation uses beat-synchronous cosine-similarity template matching.

All functions operate on decoded mono float32 audio (np.ndarray, sr).
"""

from __future__ import annotations

import math
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

# Center and normalize the KS profiles so cosine similarity is well-behaved.
_KS_MAJOR_C = _KS_MAJOR - _KS_MAJOR.mean()
_KS_MAJOR_C = _KS_MAJOR_C / np.linalg.norm(_KS_MAJOR_C)
_KS_MINOR_C = _KS_MINOR - _KS_MINOR.mean()
_KS_MINOR_C = _KS_MINOR_C / np.linalg.norm(_KS_MINOR_C)

_NOTES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

_CHORD_TEMPLATES: dict[str, np.ndarray] = {}
for _root_idx in range(12):
    _base_maj = np.zeros(12, dtype=np.float64)
    _base_maj[_root_idx] = 1.0
    _base_maj[(_root_idx + 4) % 12] = 1.0
    _base_maj[(_root_idx + 7) % 12] = 1.0
    _CHORD_TEMPLATES[f"{_NOTES[_root_idx]}:maj"] = _base_maj / math.sqrt(3)
    _base_min = np.zeros(12, dtype=np.float64)
    _base_min[_root_idx] = 1.0
    _base_min[(_root_idx + 3) % 12] = 1.0
    _base_min[(_root_idx + 7) % 12] = 1.0
    _CHORD_TEMPLATES[f"{_NOTES[_root_idx]}:min"] = _base_min / math.sqrt(3)


@dataclass(frozen=True)
class AudioKeyResult:
    tonic: str
    mode: str
    score: float
    best_score: float
    second_best_score: float
    source: str = "librosa_krumhansl"
    version: str = field(default_factory=lambda: _librosa_version())

    def to_dict(self) -> dict[str, Any]:
        return {
            "tonic": self.tonic,
            "mode": self.mode,
            "score": round(self.score, 4),
            "best_score": round(self.best_score, 4),
            "second_best_score": round(self.second_best_score, 4),
            "source": self.source,
            "version": self.version,
        }


@dataclass(frozen=True)
class AudioChordFrame:
    start_seconds: float
    end_seconds: float
    root: str
    quality: str
    score: float
    source: str = "librosa_chroma_template"


def detect_key(audio: np.ndarray, sr: float) -> AudioKeyResult | None:
    """Detect key using centered/normalized KS profiles (cosine similarity)."""
    try:
        import librosa

        y_harm = librosa.effects.harmonic(audio.astype(np.float32))
        chroma = librosa.feature.chroma_cqt(y=y_harm, sr=float(sr))
        chroma_mean = np.mean(chroma, axis=1)
        if chroma_mean.sum() <= 0:
            return None
        chroma_c = chroma_mean - chroma_mean.mean()
        chroma_c = chroma_c / (np.linalg.norm(chroma_c) + 1e-10)

        candidates: list[tuple[str, str, float]] = []
        for shift in range(12):
            rolled = np.roll(chroma_c, -shift)
            score_maj = float(np.dot(rolled, _KS_MAJOR_C))
            score_min = float(np.dot(rolled, _KS_MINOR_C))
            candidates.append((_NOTES[shift], "major", score_maj))
            candidates.append((_NOTES[shift], "minor", score_min))
        candidates.sort(key=lambda x: x[2], reverse=True)

        best = candidates[0]
        second = candidates[1] if len(candidates) > 1 else best
        return AudioKeyResult(
            tonic=best[0],
            mode=best[1],
            score=best[2],
            best_score=best[2],
            second_best_score=second[2],
        )
    except Exception:
        return None


def estimate_chords(
    audio: np.ndarray,
    sr: float,
    hop_length: int = 512,
) -> list[AudioChordFrame]:
    """Beat-synchronous chord estimation using cosine-similarity template matching."""
    import librosa

    y_harm = librosa.effects.harmonic(audio.astype(np.float32))
    chroma = librosa.feature.chroma_cqt(y=y_harm, sr=float(sr), hop_length=hop_length)
    chroma = chroma / (chroma.max(axis=0, keepdims=True) + 1e-10)

    _, beat_frames = librosa.beat.beat_track(
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
        f_start = int(beat_frames[i])
        f_end = int(beat_frames[i + 1])
        segment = np.mean(chroma[:, f_start:f_end], axis=1)
        if segment.sum() == 0:
            continue
        segment = segment - segment.mean()
        seg_norm = np.linalg.norm(segment)
        if seg_norm < 1e-10:
            continue
        segment = segment / seg_norm

        best_label = ""
        best_score = -1.0
        for label, template in _CHORD_TEMPLATES.items():
            score = float(np.dot(segment, template))
            if score > best_score:
                best_score = score
                best_label = label
        if best_label and best_score > 0.3:
            root, quality = best_label.split(":", 1)
            frames.append(
                AudioChordFrame(
                    start_seconds=float(times[i]),
                    end_seconds=float(times[i + 1]),
                    root=root,
                    quality=quality,
                    score=round(best_score, 4),
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
                score=round((prev.score + f.score) / 2, 4),
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
