"""Engine protocols and result types."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable


@dataclass(frozen=True)
class EngineProvenance:
    engine: str
    library_version: str
    model: str | None = None
    parameters: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "engine": self.engine,
            "library_version": self.library_version,
        }
        if self.model:
            d["model"] = self.model
        if self.parameters:
            d["parameters"] = self.parameters
        return d


@dataclass(frozen=True)
class TranscriptionResult:
    midi: bytes
    wav: bytes
    notes: list[dict[str, Any]]
    num_notes: int
    cleanup_report: dict[str, Any]
    provenance: EngineProvenance

    def to_dict(self) -> dict[str, Any]:
        return {
            "num_notes": self.num_notes,
            "cleanup_report": self.cleanup_report,
            "provenance": self.provenance.to_dict(),
        }


@dataclass(frozen=True)
class BeatTrackingResult:
    bpm: float
    beats: list[float]
    downbeats: list[float]
    beat_positions: list[int]
    provenance: EngineProvenance

    def to_dict(self) -> dict[str, Any]:
        return {
            "bpm": round(self.bpm, 3),
            "beat_count": len(self.beats),
            "downbeat_count": len(self.downbeats),
            "provenance": self.provenance.to_dict(),
        }


@dataclass(frozen=True)
class StructureResult:
    bpm: float
    beats: list[float]
    downbeats: list[float]
    beat_positions: list[int]
    segments: list[dict[str, Any]]
    provenance: EngineProvenance
    enabled: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "bpm": round(self.bpm, 3),
            "beat_count": len(self.beats),
            "downbeat_count": len(self.downbeats),
            "segment_count": len(self.segments),
            "segments": self.segments,
            "provenance": self.provenance.to_dict(),
        }


@dataclass(frozen=True)
class NotationResult:
    notation_midi: bytes
    musicxml: bytes
    quantization_report: dict[str, Any]
    provenance: EngineProvenance

    def to_dict(self) -> dict[str, Any]:
        return {
            "quantization_report": self.quantization_report,
            "musicxml_size": len(self.musicxml),
            "notation_midi_size": len(self.notation_midi),
            "provenance": self.provenance.to_dict(),
        }


@runtime_checkable
class TranscriptionEngine(Protocol):
    def transcribe(self, audio_bytes: bytes, fmt: str, **kwargs: Any) -> TranscriptionResult: ...


@runtime_checkable
class BeatTrackingEngine(Protocol):
    def analyze(self, wav_bytes: bytes, **kwargs: Any) -> BeatTrackingResult: ...


@runtime_checkable
class StructureEngine(Protocol):
    def analyze(self, wav_bytes: bytes, **kwargs: Any) -> StructureResult | None: ...


@runtime_checkable
class NotationEngine(Protocol):
    def convert(
        self, midi_bytes: bytes, beat_times: list[float], **kwargs: Any
    ) -> NotationResult: ...
