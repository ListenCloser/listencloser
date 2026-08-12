"""Fusion layer for reconciling audio-native and symbolic harmonic evidence.

Does not hide disagreement. Preserves both sources and annotates
consensus/conflict explicitly.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from audio.harmonic import AudioChordFrame, AudioKeyResult


@dataclass(frozen=True)
class FusedKeyResult:
    tonic: str
    mode: str
    agreement: str  # "consensus", "conflict", "symbolic_only", "audio_only"
    audio_key: AudioKeyResult | None = None
    symbolic_key: str | None = None
    symbolic_confidence: float | None = None
    confidence_source: str = "fusion"

    def to_dict(self) -> dict[str, Any]:
        return {
            "tonic": self.tonic,
            "mode": self.mode,
            "agreement": self.agreement,
            "audio_key": self.audio_key.to_dict() if self.audio_key else None,
            "symbolic_key": self.symbolic_key,
            "symbolic_confidence": (
                round(self.symbolic_confidence, 3) if self.symbolic_confidence is not None else None
            ),
            "confidence_source": self.confidence_source,
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
    symbolic_confidence: float | None,
) -> FusedKeyResult:
    """Fuse audio and symbolic key estimates.

    If both agree (same tonic+mode), returns consensus with full confidence.
    If they disagree, returns audio's estimate with conflict annotation.
    If only one source is available, returns that source's result.
    """
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
                symbolic_confidence=symbolic_confidence,
            )
        return FusedKeyResult(
            tonic=audio_key.tonic,
            mode=audio_key.mode,
            agreement="conflict",
            audio_key=audio_key,
            symbolic_key=symbolic_key,
            symbolic_confidence=symbolic_confidence,
        )
    if audio_key is not None:
        return FusedKeyResult(
            tonic=audio_key.tonic,
            mode=audio_key.mode,
            agreement="audio_only",
            audio_key=audio_key,
        )
    if symbolic_key is not None:
        parts = symbolic_key.split()
        tonic = parts[0]
        mode = parts[1] if len(parts) > 1 else "major"
        return FusedKeyResult(
            tonic=tonic,
            mode=mode,
            agreement="symbolic_only",
            symbolic_key=symbolic_key,
            symbolic_confidence=symbolic_confidence,
        )
    return FusedKeyResult(tonic="C", mode="major", agreement="symbolic_only")


def fuse_chords(
    audio_chords: list[AudioChordFrame] | None,
    symbolic_chords: list[dict[str, Any]] | None,
) -> FusedChordResult:
    a = audio_chords or []
    s = symbolic_chords or []
    consensus = 0
    conflict = 0
    for ac in a:
        found = any(
            sc.get("root", "").upper() == ac.root.upper()
            and sc.get("quality", "").lower().startswith(ac.quality.lower()[0])
            for sc in s
        )
        if found:
            consensus += 1
        else:
            conflict += 1
    return FusedChordResult(
        audio_chords=a,
        symbolic_chords=s,
        consensus_count=consensus,
        conflict_count=conflict,
        audio_only_count=max(0, len(a) - consensus),
        symbolic_only_count=max(0, len(s) - consensus),
    )
