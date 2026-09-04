from __future__ import annotations

import io
from typing import Any

import pretty_midi
import pytest

from engines.base import EngineProvenance, NotationResult
from engines.notation.pm2s_engine import PM2SNotationEngine
from engines.registry import get_notation_engine


def _performance_midi() -> bytes:
    midi = pretty_midi.PrettyMIDI(initial_tempo=120.0)
    piano = pretty_midi.Instrument(program=0)
    piano.notes.append(pretty_midi.Note(velocity=90, pitch=60, start=0.25, end=1.25))
    piano.notes.append(pretty_midi.Note(velocity=85, pitch=64, start=1.5, end=2.0))
    midi.instruments.append(piano)
    out = io.BytesIO()
    midi.write(out)
    return out.getvalue()


class _ScoreConverter:
    def __init__(self) -> None:
        self.kwargs: dict[str, Any] | None = None

    def convert(self, source: str, destination: str, **kwargs: Any) -> None:
        self.kwargs = kwargs
        # Deliberately emit MIDI that differs from the performance input. This
        # proves the downstream notation stage consumes the derived score MIDI,
        # rather than accidentally receiving the original performance MIDI.
        score = pretty_midi.PrettyMIDI(initial_tempo=120.0)
        right_hand = pretty_midi.Instrument(program=0, name="right_hand")
        right_hand.notes.append(pretty_midi.Note(velocity=80, pitch=67, start=0.0, end=1.0))
        score.instruments.append(right_hand)
        score.write(destination)


class _Importer:
    def __init__(self) -> None:
        self.inputs: list[bytes] = []
        self.kwargs: list[dict[str, Any]] = []

    def convert(
        self,
        midi_bytes: bytes,
        beat_times: list[float],
        **kwargs: Any,
    ) -> NotationResult:
        self.inputs.append(midi_bytes)
        self.kwargs.append(kwargs)
        return NotationResult(
            notation_midi=midi_bytes,
            musicxml=b'<?xml version="1.0"?><score-partwise version="4.0"></score-partwise>',
            quantization_report={"engine": "musescore", "stage": "midi_import"},
            provenance=EngineProvenance(engine="musescore", library_version="test"),
        )


def test_registry_resolves_pm2s_without_loading_model_assets() -> None:
    engine = get_notation_engine("pm2s")
    assert isinstance(engine, PM2SNotationEngine)


def test_pm2s_preserves_score_midi_and_feeds_only_it_to_musescore() -> None:
    source = _performance_midi()
    converter = _ScoreConverter()
    importer = _Importer()
    engine = PM2SNotationEngine(
        converter_factory=lambda: converter,
        musicxml_importer=importer,  # type: ignore[arg-type]
    )

    result = engine.convert(source, [0.0, 0.5, 1.0], piano_grand_staff=True)

    assert result.notation_midi != source
    assert importer.inputs == [result.notation_midi]
    learned = pretty_midi.PrettyMIDI(io.BytesIO(result.notation_midi))
    assert [note.pitch for instrument in learned.instruments for note in instrument.notes] == [67]
    assert importer.kwargs == [{"notation_ready": True, "piano_grand_staff": True}]
    assert converter.kwargs is not None
    # PM2S uses a strict note.end < end_time filter, so the adapter must pass a
    # bound beyond the performance extent or the last-ending note is omitted.
    assert converter.kwargs["end_time"] > 2.0
    assert converter.kwargs["include_time_signature"] is True
    assert converter.kwargs["include_key_signature"] is True
    assert result.provenance.engine == "pm2s"
    assert result.provenance.parameters["input_representation"] == "performance_midi"
    assert result.provenance.parameters["output_representation"] == "score_midi"
    assert (
        result.provenance.parameters["source_compatibility_patch"]
        == "midi_tempo_uint24_bound_v1"
    )
    assert result.quantization_report["score_midi_engine"] == "pm2s"
    assert result.quantization_report["musicxml_stage"] == "musescore_midi_import"
    assert result.quantization_report["source_compatibility_patch"] == "midi_tempo_uint24_bound_v1"
    assert result.quantization_report["musescore_report"] == {
        "engine": "musescore",
        "stage": "midi_import",
    }
    assert result.quantization_report["beat_grid_consumed"] is False


def test_pm2s_failure_propagates_without_invoking_musescore() -> None:
    class _FailingConverter:
        def convert(self, source: str, destination: str, **kwargs: Any) -> None:
            raise RuntimeError("pm2s inference failed")

    importer = _Importer()
    engine = PM2SNotationEngine(
        converter_factory=_FailingConverter,
        musicxml_importer=importer,  # type: ignore[arg-type]
    )

    with pytest.raises(RuntimeError, match="pm2s inference failed"):
        engine.convert(_performance_midi(), [])

    assert importer.inputs == []
