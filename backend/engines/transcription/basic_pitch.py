"""Basic Pitch transcription engine."""

from __future__ import annotations

from typing import Any

from engines.base import EngineProvenance, TranscriptionEngine, TranscriptionResult


class BasicPitchEngine(TranscriptionEngine):
    ENGINE = "basic_pitch"

    def __init__(
        self,
        onset_threshold: float = 0.5,
        frame_threshold: float = 0.3,
    ) -> None:
        self._onset_threshold = onset_threshold
        self._frame_threshold = frame_threshold
        self._version: str | None = None

    @property
    def provenance(self) -> EngineProvenance:
        return EngineProvenance(
            engine=self.ENGINE,
            library_version=self._version or _basic_pitch_version(),
            parameters={
                "onset_threshold": self._onset_threshold,
                "frame_threshold": self._frame_threshold,
            },
        )

    def transcribe(self, audio_bytes: bytes, fmt: str, **kwargs: Any) -> TranscriptionResult:
        import music_features as mf

        result = mf.transcribe_audio(
            audio_bytes,
            fmt=fmt,
            onset_threshold=self._onset_threshold,
            frame_threshold=self._frame_threshold,
        )
        return TranscriptionResult(
            midi=result["midi"],
            wav=result["wav"],
            notes=result["notes"],
            num_notes=result["num_notes"],
            cleanup_report=result.get("cleanup_report", {}),
            provenance=self.provenance,
            model_note_events=result.get("model_note_events", []),
            tempo_is_placeholder=True,
            meter_is_placeholder=True,
            supports_meter=False,
        )


def _basic_pitch_version() -> str:
    try:
        from importlib.metadata import version

        return version("basic-pitch")
    except Exception:
        return "unknown"
