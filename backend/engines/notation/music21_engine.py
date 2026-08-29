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

        if piano_grand_staff:
            musicxml = _grand_staff_musicxml(
                notation_midi,
                beat_times=beat_times,
                downbeats=downbeats,
                beat_positions=beat_positions,
            )
        else:
            musicxml = mf.convert_format(
                notation_midi,
                "midi",
                "musicxml",
                notation_ready=notation_ready,
                piano_grand_staff=False,
            )
        return NotationResult(
            notation_midi=notation_midi,
            musicxml=musicxml,
            quantization_report=quant_report,
            provenance=self.provenance,
        )


def _grand_staff_musicxml(
    midi_bytes: bytes,
    *,
    beat_times: list[float],
    downbeats: list[float] | None,
    beat_positions: list[int] | None,
) -> bytes:
    """Engrave grand staff using source-grid timing when meter is supported.

    Basic Pitch MIDI carries placeholder tempo/meter metadata. The Score worker
    already has source-audio beat/downbeat evidence, so pass that evidence into
    grand-staff reconstruction instead of silently reinterpreting note seconds
    against the placeholder MIDI tempo. If no trustworthy meter can be inferred,
    retain the historical path rather than inventing one here.
    """
    import contextlib
    import copy
    import os
    import tempfile

    from notation.grid import build_metrical_grid
    from notation.staffing import grand_staff_from_midi

    metric_grid = build_metrical_grid(
        beat_times,
        downbeats=downbeats,
        beat_positions=beat_positions,
    )
    if metric_grid.inferred_meter is not None and metric_grid.global_beats():
        score = grand_staff_from_midi(
            midi_bytes,
            beat_times=metric_grid.beats,
            meter_signature=metric_grid.inferred_meter,
        )
    else:
        score = grand_staff_from_midi(midi_bytes)

    # Preserve the existing truthfulness gate for key signatures. This mirrors
    # music_features.convert_format without routing grand-staff timing back
    # through the placeholder MIDI metadata.
    with contextlib.suppress(Exception):
        analyzed = score.analyze("key")
        corr = analyzed.correlationCoefficient
        if corr is not None and corr >= 0.8:
            from music21 import key as key_mod

            signature = key_mod.KeySignature(analyzed.sharps)
            for part in score.parts:
                first_measure = part.getElementsByClass("Measure")[0]
                first_measure.insert(0, copy.deepcopy(signature))

    with tempfile.TemporaryDirectory() as td:
        out_path = os.path.join(td, "output.xml")
        score.write("musicxml", fp=out_path)
        with open(out_path, "rb") as file_handle:
            return file_handle.read()


def _music21_version() -> str:
    try:
        import music21

        return music21.__version__  # type: ignore[attr-defined]
    except Exception:
        return "unknown"
