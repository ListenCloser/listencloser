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
    model_note_events: list[dict[str, Any]] = field(default_factory=list)
    tempo_is_placeholder: bool = False
    meter_is_placeholder: bool = False
    supports_meter: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "num_notes": self.num_notes,
            "cleanup_report": self.cleanup_report,
            "provenance": self.provenance.to_dict(),
            "tempo_is_placeholder": self.tempo_is_placeholder,
            "meter_is_placeholder": self.meter_is_placeholder,
            "supports_meter": self.supports_meter,
        }


@dataclass(frozen=True)
class BeatTrackingResult:
    bpm: float | None
    beats: list[float]
    downbeats: list[float] | None
    beat_positions: list[int] | None
    provenance: EngineProvenance

    def to_dict(self) -> dict[str, Any]:
        return {
            "bpm": round(self.bpm, 3) if self.bpm is not None else None,
            "beat_count": len(self.beats),
            "downbeat_count": len(self.downbeats) if self.downbeats is not None else None,
            "provenance": self.provenance.to_dict(),
        }


@dataclass(frozen=True)
class StructureResult:
    bpm: float
    beats: list[float]
    downbeats: list[float] | None
    beat_positions: list[int]
    segments: list[dict[str, Any]]
    provenance: EngineProvenance

    def evidence(self) -> dict[str, Any]:
        return {
            "bpm": self.bpm,
            "beat_count": len(self.beats),
            "downbeat_count": len(self.downbeats) if self.downbeats is not None else 0,
            "segment_count": len(self.segments),
            "engine": self.provenance.engine,
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "bpm": round(self.bpm, 3),
            "beat_count": len(self.beats),
            "downbeat_count": len(self.downbeats) if self.downbeats is not None else None,
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


@dataclass(frozen=True)
class HarmonyResult:
    key: dict[str, Any] | None
    chords: list[dict[str, Any]]
    roman_numerals: list[dict[str, Any]]
    cadences: list[dict[str, Any]]
    voice_leading: dict[str, Any] | None
    phrases: list[dict[str, Any]]
    provenance: EngineProvenance
    component_provenance: dict[str, EngineProvenance] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "chords": self.chords,
            "roman_numerals": self.roman_numerals,
            "cadences": self.cadences,
            "voice_leading": self.voice_leading,
            "phrases": self.phrases,
            "provenance": self.provenance.to_dict(),
            "component_provenance": {k: v.to_dict() for k, v in self.component_provenance.items()},
        }


@dataclass(frozen=True)
class MelodyResult:
    melody: dict[str, Any] | None
    provenance: EngineProvenance

    def to_dict(self) -> dict[str, Any]:
        return {
            "melody": self.melody,
            "provenance": self.provenance.to_dict(),
        }


@runtime_checkable
class NotationEngine(Protocol):
    def convert(self, midi_bytes: bytes, beat_times: list[float], **kwargs: Any) -> NotationResult:
        """Produce notated MIDI and MusicXML from a performance MIDI and beat grid.

        Interface contract (engines must honor these when present; unknown
        options may be ignored):

        - ``adaptive``: build the metrical grid and quantize per-measure from
          beat/downbeat positions, instead of a fixed subdivision grid.
        - ``downbeats``: beat-position subset that anchors measure boundaries.
        - ``beat_positions``: metrical position (1-based step) of each beat.
        - ``notation_ready``: input MIDI is already quantized notation; do not
          re-quantize or infer meter.
        - ``piano_grand_staff``: engrave treble+bass staves instead of a single
          staff.

        These options describe requested notation semantics, not a specific
        library.  Returns a NotationResult.
        """


@runtime_checkable
class HarmonyEngine(Protocol):
    def analyze(
        self,
        midi_bytes: bytes,
        tempo_bpm: float | None = None,
        audio_bytes: bytes | None = None,
        **kwargs: Any,
    ) -> HarmonyResult:
        """Harmonic analysis of music input.

        Input modalities vary by engine:
          - lv-chordia: audio-native (uses audio_bytes, ignores midi_bytes)
          - music21: symbolic (uses midi_bytes, ignores audio_bytes)

        Returns a normalized HarmonyResult (key, chords, roman numerals,
        cadences, voice leading, phrases) with provenance.
        """


@runtime_checkable
class MelodyEngine(Protocol):
    def analyze(self, midi_bytes: bytes, **kwargs: Any) -> MelodyResult:
        """Symbolic melody extraction from a MIDI file.

        Returns a normalized MelodyResult (melody features or None when no
        melodic line is detected) with provenance.
        """
