from __future__ import annotations

import io
import shutil
from pathlib import Path
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


class _CopyConverter:
    def __init__(self) -> None:
        self.kwargs: dict[str, Any] | None = None

    def convert(self, source: str, destination: str, **kwargs: Any) -> None:
        self.kwargs = kwargs
        shutil.copyfile(source, destination)


class _Exporter:
    def __init__(self) -> None:
        self.inputs: list[bytes] = []

    def convert(self, midi_bytes: bytes, beat_times: list[float], **kwargs: Any) -> NotationResult:
        self.inputs.append(midi_bytes)
        return NotationResult(
            notation_midi=midi_bytes,
            musicxml=b'<?xml version="1.0"?><score-partwise version="4.0"></score-partwise>',
            quantization_report={"engine": "musescore"},
            provenance=EngineProvenance(engine="musescore", library_version="test"),
        )


def test_registry_resolves_pm2s_without_loading_model_assets() -> None:
    engine = get_notation_engine("pm2s")
    assert isinstance(engine, PM2SNotationEngine)


def test_pm2s_preserves_learned_score_midi_and_passes_explicit_end_time() -> None:
    source = _performance_midi()
    converter = _CopyConverter()
    exporter = _Exporter()
    engine = PM2SNotationEngine(
        converter_factory=lambda: converter,
        musicxml_exporter=exporter,  # type: ignore[arg-type]
    )

    result = engine.convert(source, [0.0, 0.5, 1.0], piano_grand_staff=True)

    assert result.notation_midi == source
    assert exporter.inputs == [source]
    assert converter.kwargs is not None
    assert converter.kwargs["end_time"] == pytest.approx(2.0)
    assert converter.kwargs["include_time_signature"] is True
    assert converter.kwargs["include_key_signature"] is True
    assert result.provenance.engine == "pm2s"
    assert result.quantization_report["score_interpreter"] == "pm2s"
    assert result.quantization_report["musicxml_exporter"] == "musescore"
    assert result.quantization_report["beat_grid_consumed"] is False


def test_pm2s_failure_propagates_without_invoking_exporter(tmp_path: Path) -> None:
    class _FailingConverter:
        def convert(self, source: str, destination: str, **kwargs: Any) -> None:
            raise RuntimeError("pm2s inference failed")

    exporter = _Exporter()
    engine = PM2SNotationEngine(
        converter_factory=_FailingConverter,
        musicxml_exporter=exporter,  # type: ignore[arg-type]
    )

    with pytest.raises(RuntimeError, match="pm2s inference failed"):
        engine.convert(_performance_midi(), [])

    assert exporter.inputs == []
