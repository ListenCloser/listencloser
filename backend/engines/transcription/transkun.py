"""Transkun transcription engine."""

from __future__ import annotations

import os
import tempfile
from typing import Any

from engines.base import EngineProvenance, TranscriptionEngine, TranscriptionResult


class TranskunEngine(TranscriptionEngine):
    ENGINE = "transkun"
    DEFAULT_SAMPLE_RATE = 44100

    def __init__(
        self,
        onset_threshold: float = 0.5,
        frame_threshold: float = 0.3,
        device: str = "cpu",
    ) -> None:
        self._onset_threshold = onset_threshold
        self._frame_threshold = frame_threshold
        self._device = device
        self._model = None
        self._version: str | None = None

    @property
    def provenance(self) -> EngineProvenance:
        return EngineProvenance(
            engine=self.ENGINE,
            library_version=self._version or _transkun_version(),
            model="transkun_2.0",
            parameters={
                "onset_threshold": self._onset_threshold,
                "frame_threshold": self._frame_threshold,
                "device": self._device,
            },
        )

    def _prepare(self) -> None:
        if self._model is not None:
            return

        try:
            import torch
            import moduleconf
            from transkun.transcribe import readAudio, writeMidi

            import pkg_resources
            default_weight = pkg_resources.resource_filename("transkun.transcribe", "pretrained/2.0.pt")
            default_conf = pkg_resources.resource_filename("transkun.transcribe", "pretrained/2.0.conf")

            conf_manager = moduleconf.parseFromFile(default_conf)
            ModelClass = conf_manager["Model"].module.TransKun
            conf = conf_manager["Model"].config

            checkpoint = torch.load(default_weight, map_location=self._device)
            self._model = ModelClass(conf=conf).to(self._device)

            if "best_state_dict" in checkpoint:
                self._model.load_state_dict(checkpoint["best_state_dict"], strict=False)
            else:
                self._model.load_state_dict(checkpoint["state_dict"], strict=False)

            self._model.eval()
        except Exception as e:
            raise RuntimeError(f"Transkun prepare failed: {e}") from e

    def transcribe(self, audio_bytes: bytes, fmt: str = "wav", **kwargs: Any) -> TranscriptionResult:
        import io

        self._prepare()
        if self._model is None:
            raise RuntimeError("Transkun not available")

        from transkun.transcribe import readAudio, writeMidi
        import torch

        # Detect audio format from content bytes
        detected_fmt = fmt
        if audio_bytes[:4] == b"RIFF":
            detected_fmt = "wav"
        elif audio_bytes[:4] == b"OggS":
            detected_fmt = "ogg"
        elif audio_bytes[:2] == b"\xff\xfb":
            detected_fmt = "mp3"
        elif len(audio_bytes) >= 12 and audio_bytes[4:8] == b"ftyp":
            detected_fmt = "m4a"

        # Write audio to temp file for Transkun's readAudio
        with tempfile.NamedTemporaryFile(suffix=f".{detected_fmt}", delete=False) as f:
            f.write(audio_bytes)
            temp_audio = f.name

        temp_midi = temp_audio.rsplit(".", 1)[0] + ".mid"

        try:
            fs, audio = readAudio(temp_audio)

            torch.set_grad_enabled(False)

            # Resample if needed
            if fs != self._model.fs:
                try:
                    import soxr
                    audio = soxr.resample(audio, fs, self._model.fs)
                except ImportError:
                    pass  # skip resampling if soxr not available

            x = torch.from_numpy(audio).to(self._device)

            notes_est = self._model.transcribe(
                x,
                stepInSecond=kwargs.get("segment_hop_size"),
                segmentSizeInSecond=kwargs.get("segment_size"),
                discardSecondHalf=False,
            )

            writeMidi(notes_est).write(temp_midi)

            import pretty_midi
            midi_data = pretty_midi.PrettyMIDI(temp_midi)

            notes = []
            for instrument in midi_data.instruments:
                for note in instrument.notes:
                    notes.append({
                        "pitch": note.pitch,
                        "start": note.start,
                        "end": note.end,
                        "velocity": note.velocity,
                    })

            midi_bytes = io.BytesIO()
            midi_data.write(midi_bytes)
            midi_bytes = midi_bytes.getvalue()

            return TranscriptionResult(
                midi=midi_bytes,
                wav=b"",
                notes=notes,
                num_notes=len(notes),
                cleanup_report={},
                provenance=self.provenance,
                model_note_events=[],
                tempo_is_placeholder=True,
                meter_is_placeholder=True,
                supports_meter=False,
            )
        finally:
            for p in [temp_audio, temp_midi]:
                try:
                    os.unlink(p)
                except Exception:
                    pass


def _transkun_version() -> str:
    try:
        from importlib.metadata import version
        return version("transkun")
    except Exception:
        return "unknown"