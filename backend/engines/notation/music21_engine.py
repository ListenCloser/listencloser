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
        *,
        adaptive: bool = False,
        downbeats: list[float] | None = None,
        beat_positions: list[int] | None = None,
        notation_ready: bool = False,
        piano_grand_staff: bool = False,
        **kwargs: Any,
    ) -> NotationResult:
        """Quantize a performance MIDI against a beat grid and engrave a score.

        ``adaptive=True`` selects a per-measure grid from ``downbeats`` /
        ``beat_positions`` via adaptive quantization; otherwise a fixed
        subdivision grid is used. ``notation_ready`` skips performance-level
        re-quantization, and ``piano_grand_staff`` engraves treble+bass staves.
        Unrecognized options are ignored so callers can pass interface
        contract options that a different engine may support.
        """
        import music_features as mf

        if adaptive:
            notation_midi, quant_report = mf.adaptive_notation_from_performance(
                midi_bytes, beat_times, downbeats=downbeats, beat_positions=beat_positions
            )
        else:
            notation_midi, quant_report = mf.notation_midi_from_performance(midi_bytes, beat_times)
        musicxml = mf.convert_format(
            notation_midi,
            "midi",
            "musicxml",
            notation_ready=notation_ready,
            piano_grand_staff=piano_grand_staff,
        )
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
