"""Music21 notation engine."""

from __future__ import annotations

from typing import Any

from engines.base import EngineProvenance, NotationEngine, NotationResult


class Music21NotationEngine(NotationEngine):
    ENGINE = "music21"

    def __init__(self) -> None:
        pass

    @property
    def provenance(self) -> EngineProvenance:
        return EngineProvenance(
            engine=self.ENGINE,
            library_version=_music21_version(),
        )

    def convert(
        self,
        midi_bytes: bytes,
        beat_times: list[float],
        **kwargs: Any,
    ) -> NotationResult:
        import music_features as mf

        notation_midi, quant_report = mf.notation_midi_from_performance(midi_bytes, beat_times)
        musicxml = mf.convert_format(notation_midi, "midi", "musicxml")
        return NotationResult(
            notation_midi=notation_midi,
            musicxml=musicxml,
            quantization_report=quant_report,
            provenance=self.provenance,
        )


def _music21_version() -> str:
    try:
        import music21

        return music21.__version__  # type: ignore[attr-defined]
    except Exception:
        return "unknown"
