"""PM2S learned performance-MIDI to score-MIDI adapter.

PM2S owns the learned performance-MIDI -> score-MIDI stage. The resulting
score MIDI is then imported by MuseScore to obtain MusicXML for the existing
OSMD Score path. MuseScore is intentionally not described as a passive
serializer: its MIDI importer may make additional notation decisions.

The PM2S score MIDI remains the returned ``notation_midi`` artifact so callers
can inspect the learned intermediate separately from the final MusicXML.
Failures never fall back to importing the original performance MIDI.
"""

from __future__ import annotations

import io
import os
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pretty_midi

from engines.base import EngineProvenance, NotationResult
from engines.notation.musescore_engine import MuseScoreNotationEngine


class PM2SNotationEngine:
    """Convert performance MIDI to score MIDI with PM2S, then MusicXML."""

    ENGINE = "pm2s"
    SOURCE_COMMIT = "9586f91cd16aaa50dbb82f720f6a34a3e0186f47"
    MODEL_RECORD = "zenodo:10520196"

    def __init__(
        self,
        *,
        converter_factory: Callable[..., Any] | None = None,
        musicxml_importer: MuseScoreNotationEngine | None = None,
    ) -> None:
        self._converter_factory = converter_factory
        self._musicxml_importer = musicxml_importer
        self._converter: Any | None = None

    @property
    def provenance(self) -> EngineProvenance:
        return EngineProvenance(
            engine=self.ENGINE,
            library_version=self.SOURCE_COMMIT,
            model="CRNNJointPM2S",
            parameters={
                "model_record": self.MODEL_RECORD,
                "input_representation": "performance_midi",
                "output_representation": "score_midi",
                "score_midi_engine": "pm2s",
                "musicxml_stage": "musescore_midi_import",
                "beat_grid_consumed": False,
            },
        )

    def _get_converter(self) -> Any:
        if self._converter is not None:
            return self._converter

        if self._converter_factory is not None:
            self._converter = self._converter_factory()
            return self._converter

        try:
            from pm2s.pm2s import CRNNJointPM2S
        except ImportError as exc:
            raise RuntimeError(
                "PM2S is not installed in the worker image; the PM2S notation "
                "engine cannot run"
            ) from exc

        model_root = os.environ.get("PM2S_MODEL_DIR")
        if not model_root:
            raise RuntimeError("PM2S_MODEL_DIR must point to pinned PM2S model assets")
        root = Path(model_root)
        model_paths = {
            "model_path_beat": root / "RNNJointBeatModel.pth",
            "model_path_hand_part": root / "RNNHandPartModel.pth",
            "model_path_key_sig": root / "RNNKeySignatureModel.pth",
            "model_path_time_sig": root / "CNNTimeSignatureModel.pth",
        }
        missing = [str(path) for path in model_paths.values() if not path.is_file()]
        if missing:
            raise RuntimeError(f"PM2S model assets are missing: {', '.join(missing)}")

        self._converter = CRNNJointPM2S(**{name: str(path) for name, path in model_paths.items()})
        return self._converter

    def _get_musicxml_importer(self) -> MuseScoreNotationEngine:
        if self._musicxml_importer is None:
            self._musicxml_importer = MuseScoreNotationEngine()
        return self._musicxml_importer

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
        if not midi_bytes.startswith(b"MThd"):
            raise ValueError("PM2S notation input must be a MIDI file")

        performance = pretty_midi.PrettyMIDI(io.BytesIO(midi_bytes))
        input_notes = sum(len(instrument.notes) for instrument in performance.instruments)
        end_time = float(performance.get_end_time())
        if end_time <= 0:
            raise ValueError("PM2S notation input must contain positive-duration MIDI")

        with tempfile.TemporaryDirectory(prefix="listencloser-pm2s-") as td:
            root = Path(td)
            input_path = root / "performance.mid"
            output_path = root / "score.mid"
            input_path.write_bytes(midi_bytes)

            converter = self._get_converter()
            converter.convert(
                str(input_path),
                str(output_path),
                start_time=0.0,
                # PM2S 1.1 documents None as supported, but its time-to-tick
                # implementation consumes end_time arithmetically. Pass the
                # exact performance extent explicitly instead of relying on the
                # fragile default.
                end_time=end_time,
                include_time_signature=True,
                include_key_signature=True,
            )

            if not output_path.is_file() or output_path.stat().st_size == 0:
                raise RuntimeError("PM2S conversion did not produce score MIDI")
            score_midi = output_path.read_bytes()

        if not score_midi.startswith(b"MThd"):
            raise RuntimeError("PM2S output is not recognizable MIDI")

        learned = pretty_midi.PrettyMIDI(io.BytesIO(score_midi))
        output_notes = sum(len(instrument.notes) for instrument in learned.instruments)
        if input_notes and not output_notes:
            raise RuntimeError("PM2S dropped every input note")

        # Feed only the learned score-MIDI artifact downstream. MuseScore's MIDI
        # import can still make notation decisions, so provenance names this an
        # import stage rather than pretending it is a lossless serializer.
        imported = self._get_musicxml_importer().convert(
            score_midi,
            [],
            notation_ready=True,
            piano_grand_staff=piano_grand_staff,
        )

        return NotationResult(
            notation_midi=score_midi,
            musicxml=imported.musicxml,
            quantization_report={
                "engine": self.ENGINE,
                "input_representation": "performance_midi",
                "output_representation": "score_midi",
                "score_midi_engine": "pm2s",
                "musicxml_stage": "musescore_midi_import",
                "source_commit": self.SOURCE_COMMIT,
                "model_record": self.MODEL_RECORD,
                "beat_grid_available": bool(beat_times),
                "beat_grid_consumed": False,
                "beat_count": len(beat_times),
                "downbeat_count": len(downbeats) if downbeats is not None else None,
                "beat_positions_available": beat_positions is not None,
                "adaptive_requested": adaptive,
                "notation_ready_requested": notation_ready,
                "piano_grand_staff_requested": piano_grand_staff,
                "input_notes": input_notes,
                "output_notes": output_notes,
                "musescore_report": imported.quantization_report,
            },
            provenance=self.provenance,
        )
