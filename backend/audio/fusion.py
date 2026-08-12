"""Fusion layer for reconciling audio-native and symbolic harmonic evidence.

Preserves both sources. Does not hide disagreement or fabricate claims.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from audio.harmonic import AudioChordFrame, AudioKeyResult

_QUALITY_MAP = {
    "major": "maj",
    "maj": "maj",
    "M": "maj",
    "": "maj",
    "minor": "min",
    "min": "min",
    "m": "min",
    "diminished": "dim",
    "dim": "dim",
    "augmented": "aug",
    "aug": "aug",
    "dominant": "dom",
    "dom": "dom",
}

_PC_SHARP = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
_PC_FLAT = ["C", "Db", "D", "Eb", "E", "F", "Gb", "G", "Ab", "A", "Bb", "B"]


def _pitch_class(root: str) -> int:
    """Map a root spelling (sharp or flat) to a pitch class integer 0..11."""
    r = (root or "").strip()
    if r in _PC_SHARP:
        return _PC_SHARP.index(r)
    if r in _PC_FLAT:
        return _PC_FLAT.index(r)
    # Fallback: try single letter
    if r.upper() in _PC_SHARP:
        return _PC_SHARP.index(r.upper())
    return -1


def _canonical(root: str, quality: str) -> tuple[int, str]:
    q = quality or ""
    return (
        _pitch_class(root),
        _QUALITY_MAP.get(q, _QUALITY_MAP.get(q.lower(), q.lower())),
    )


@dataclass(frozen=True)
class FusedKeyResult:
    tonic: str | None
    mode: str | None
    agreement: str
    audio_key: AudioKeyResult | None = None
    symbolic_key: str | None = None
    symbolic_score: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "tonic": self.tonic,
            "mode": self.mode,
            "agreement": self.agreement,
            "audio_key": self.audio_key.to_dict() if self.audio_key else None,
            "symbolic_key": self.symbolic_key,
            "symbolic_score": self.symbolic_score,
        }


@dataclass(frozen=True)
class FusedChordResult:
    audio_chords: list[AudioChordFrame] = field(default_factory=list)
    symbolic_chords: list[dict[str, Any]] = field(default_factory=list)
    consensus_count: int = 0
    conflict_count: int = 0
    audio_only_count: int = 0
    symbolic_only_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "audio_count": len(self.audio_chords),
            "symbolic_count": len(self.symbolic_chords),
            "consensus_count": self.consensus_count,
            "conflict_count": self.conflict_count,
            "audio_only_count": self.audio_only_count,
            "symbolic_only_count": self.symbolic_only_count,
        }


def fuse_key(
    audio_key: AudioKeyResult | None,
    symbolic_key: str | None,
    symbolic_score: float | None,
) -> FusedKeyResult:
    if audio_key is None and symbolic_key is None:
        return FusedKeyResult(tonic=None, mode=None, agreement="unavailable")

    if audio_key is not None and symbolic_key is not None:
        audio_str = f"{audio_key.tonic} {audio_key.mode}".lower()
        sym_str = symbolic_key.lower()
        if audio_str == sym_str:
            return FusedKeyResult(
                tonic=audio_key.tonic,
                mode=audio_key.mode,
                agreement="consensus",
                audio_key=audio_key,
                symbolic_key=symbolic_key,
                symbolic_score=symbolic_score,
            )
        return FusedKeyResult(
            tonic=None,
            mode=None,
            agreement="conflict",
            audio_key=audio_key,
            symbolic_key=symbolic_key,
            symbolic_score=symbolic_score,
        )

    if audio_key is not None:
        return FusedKeyResult(
            tonic=audio_key.tonic,
            mode=audio_key.mode,
            agreement="audio_only",
            audio_key=audio_key,
        )
    return FusedKeyResult(
        tonic=symbolic_key.split()[0] if " " in symbolic_key else symbolic_key,
        mode=symbolic_key.split()[1] if " " in symbolic_key else "major",
        agreement="symbolic_only",
        symbolic_key=symbolic_key,
        symbolic_score=symbolic_score,
    )


def fuse_chords(
    audio_chords: list[AudioChordFrame] | None,
    symbolic_chords: list[dict[str, Any]] | None,
    onset_tolerance: float = 1.0,
) -> FusedChordResult:
    """Match chords temporally first, then classify each pair.

    One-to-one assignment by nearest onset within tolerance. A matched pair is
    consensus if its canonical identity agrees, otherwise conflict. Only truly
    unmatched events count as audio_only / symbolic_only.
    """
    a = audio_chords or []
    s = symbolic_chords or []
    consensus = 0
    conflict = 0
    matched_symbolic: set[int] = set()

    for ac in a:
        # Choose the temporally closest unmatched symbolic event.
        best_j: int | None = None
        best_dist = float("inf")
        for j, sc in enumerate(s):
            if j in matched_symbolic:
                continue
            dist = abs(ac.start_seconds - float(sc.get("start", 0)))
            if dist <= onset_tolerance and dist < best_dist:
                best_dist = dist
                best_j = j

        if best_j is None:
            continue  # unmatched audio -> audio_only
        matched_symbolic.add(best_j)

        ac_canon = _canonical(ac.root, ac.quality)
        sc = s[best_j]
        sc_canon = _canonical(sc.get("root", ""), sc.get("quality", ""))
        if ac_canon == sc_canon:
            consensus += 1
        else:
            conflict += 1

    audio_only = len(a) - (consensus + conflict)
    symbolic_only = len(s) - len(matched_symbolic)

    return FusedChordResult(
        audio_chords=a,
        symbolic_chords=s,
        consensus_count=consensus,
        conflict_count=conflict,
        audio_only_count=audio_only,
        symbolic_only_count=symbolic_only,
    )


def _onsets_match(a_start: float, s_start: float, tolerance: float) -> bool:
    return abs(a_start - s_start) <= tolerance
