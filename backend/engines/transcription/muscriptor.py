"""Isolated MuScriptor transcription challenger.

MuScriptor's public runtime currently requires a dependency graph that is
materially different from ListenCloser's normal worker.  Keep it behind an
explicit child-Python boundary: the normal worker writes the source audio,
invokes a separately provisioned/pinned MuScriptor environment, then parses the
emitted MIDI back into the repository-owned ``TranscriptionResult`` contract.

The released ``muscriptor-small`` checkpoint is CC BY-NC 4.0 and gated on
Hugging Face.  This adapter is therefore internal/evaluation-only under the
current terms and deliberately requires a local checkpoint plus its expected
SHA-256.  Runtime inference is forced offline; a user's request must never
trigger an unpinned model download.
"""

from __future__ import annotations

import hashlib
import io
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from engines.base import EngineProvenance, TranscriptionEngine, TranscriptionResult

MUSCRIPTOR_UPSTREAM_REVISION = "7f213afecf23bd6a1b8672aa223690ee9807cefb"
MUSCRIPTOR_PACKAGE_VERSION = "0.3.0"
MUSCRIPTOR_MODEL = "muscriptor-small"
MUSCRIPTOR_MODEL_REPO = "MuScriptor/muscriptor-small"
MUSCRIPTOR_CODE_LICENSE = "MIT"
MUSCRIPTOR_WEIGHT_LICENSE = "CC-BY-NC-4.0"

_DEFAULT_TIMEOUT_SECONDS = 30 * 60
_ALLOWED_FORMATS = {"wav", "mp3", "m4a", "flac", "ogg", "aac"}


class MuScriptorEngine(TranscriptionEngine):
    """Run MuScriptor-small in a separately provisioned Python environment."""

    ENGINE = "muscriptor"

    def __init__(
        self,
        *,
        runtime_python: str | None = None,
        model_path: str | None = None,
        model_sha256: str | None = None,
        device: str = "cpu",
        timeout_seconds: float = _DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        if timeout_seconds <= 0:
            raise ValueError("MuScriptor timeout must be positive")
        self._runtime_python = runtime_python or os.getenv("MUSCRIPTOR_RUNTIME_PYTHON")
        self._model_path = model_path or os.getenv("MUSCRIPTOR_MODEL_PATH")
        self._model_sha256 = model_sha256 or os.getenv("MUSCRIPTOR_MODEL_SHA256")
        self._device = device
        self._timeout_seconds = timeout_seconds
        self._verified_model: tuple[str, int, int] | None = None

    @property
    def provenance(self) -> EngineProvenance:
        parameters: dict[str, Any] = {
            "device": self._device,
            "isolated_runtime": True,
            "upstream_revision": MUSCRIPTOR_UPSTREAM_REVISION,
            "model_repo": MUSCRIPTOR_MODEL_REPO,
            "code_license": MUSCRIPTOR_CODE_LICENSE,
            "weight_license": MUSCRIPTOR_WEIGHT_LICENSE,
            "commercial_default_eligible": False,
            "tempo_detection": False,
        }
        if self._model_sha256:
            parameters["checkpoint_sha256"] = self._model_sha256.lower()
        return EngineProvenance(
            engine=self.ENGINE,
            library_version=MUSCRIPTOR_PACKAGE_VERSION,
            model=MUSCRIPTOR_MODEL,
            parameters=parameters,
        )

    def _runtime_paths(self) -> tuple[Path, Path]:
        if not self._runtime_python:
            raise RuntimeError(
                "MuScriptor requires MUSCRIPTOR_RUNTIME_PYTHON pointing to the "
                "isolated pinned runtime"
            )
        if not self._model_path:
            raise RuntimeError(
                "MuScriptor requires MUSCRIPTOR_MODEL_PATH pointing to the local "
                "gated muscriptor-small checkpoint"
            )
        if not self._model_sha256:
            raise RuntimeError(
                "MuScriptor requires MUSCRIPTOR_MODEL_SHA256 so the gated checkpoint "
                "identity is fail-closed"
            )

        runtime_python = Path(self._runtime_python)
        model_path = Path(self._model_path)
        if not runtime_python.is_file():
            raise RuntimeError(f"MuScriptor runtime Python not found: {runtime_python}")
        if not model_path.is_file():
            raise RuntimeError(f"MuScriptor checkpoint not found: {model_path}")
        self._verify_checkpoint(model_path)
        return runtime_python, model_path

    def _verify_checkpoint(self, model_path: Path) -> None:
        stat = model_path.stat()
        cache_key = (str(model_path.resolve()), stat.st_size, stat.st_mtime_ns)
        if self._verified_model == cache_key:
            return

        digest = hashlib.sha256()
        with model_path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        actual = digest.hexdigest()
        expected = str(self._model_sha256).lower()
        if actual != expected:
            raise RuntimeError(
                "MuScriptor checkpoint SHA-256 mismatch; refusing to run an "
                "unpinned model asset"
            )
        self._verified_model = cache_key

    def transcribe(
        self, audio_bytes: bytes, fmt: str = "wav", **kwargs: Any
    ) -> TranscriptionResult:
        runtime_python, model_path = self._runtime_paths()
        source_format = _normalize_format(fmt, audio_bytes)

        with tempfile.TemporaryDirectory(prefix="listencloser-muscriptor-") as tmp:
            root = Path(tmp)
            input_path = root / f"source.{source_format}"
            output_path = root / "transcription.mid"
            input_path.write_bytes(audio_bytes)

            command = [
                str(runtime_python),
                "-m",
                "muscriptor",
                "transcribe",
                str(input_path),
                "--output",
                str(output_path),
                "--format",
                "midi",
                "--model",
                str(model_path),
                "--device",
                self._device,
                "--batch-size",
                "1",
                "--detect-tempo",
                "false",
            ]
            env = os.environ.copy()
            env["HF_HUB_OFFLINE"] = "1"
            env["HF_DATASETS_OFFLINE"] = "1"

            try:
                completed = subprocess.run(
                    command,
                    capture_output=True,
                    text=True,
                    env=env,
                    timeout=self._timeout_seconds,
                    check=False,
                )
            except subprocess.TimeoutExpired as exc:
                raise RuntimeError("MuScriptor transcription timed out") from exc

            if completed.returncode != 0:
                stderr_tail = (completed.stderr or "")[-1500:]
                raise RuntimeError(
                    "MuScriptor isolated runtime failed"
                    + (f": {stderr_tail}" if stderr_tail else "")
                )
            if not output_path.is_file():
                raise RuntimeError("MuScriptor completed without producing MIDI")

            midi_bytes = output_path.read_bytes()
            if len(midi_bytes) < 14 or not midi_bytes.startswith(b"MThd"):
                raise RuntimeError("MuScriptor produced an invalid MIDI file")
            notes, model_note_events = _parse_midi(midi_bytes)

        return TranscriptionResult(
            midi=midi_bytes,
            wav=b"",
            notes=notes,
            num_notes=len(notes),
            cleanup_report={
                "instrument_labels": "model_emitted_program_groups",
                "velocity_semantics": "MIDI exporter value; MuScriptor does not recover velocity",
                "runtime": "isolated",
            },
            provenance=self.provenance,
            model_note_events=model_note_events,
            tempo_is_placeholder=True,
            meter_is_placeholder=True,
            supports_meter=False,
        )


def _normalize_format(fmt: str, audio_bytes: bytes) -> str:
    detected = str(fmt or "wav").lower().lstrip(".")
    if audio_bytes[:4] == b"RIFF":
        detected = "wav"
    elif audio_bytes[:4] == b"OggS":
        detected = "ogg"
    elif audio_bytes[:3] == b"ID3" or audio_bytes[:2] in {b"\xff\xfb", b"\xff\xf3", b"\xff\xf2"}:
        detected = "mp3"
    elif len(audio_bytes) >= 12 and audio_bytes[4:8] == b"ftyp":
        detected = "m4a"
    elif audio_bytes[:4] == b"fLaC":
        detected = "flac"
    if detected not in _ALLOWED_FORMATS:
        raise ValueError(f"unsupported MuScriptor input format: {detected}")
    return detected


def _parse_midi(midi_bytes: bytes) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    import pretty_midi

    midi = pretty_midi.PrettyMIDI(io.BytesIO(midi_bytes))
    notes: list[dict[str, Any]] = []
    model_events: list[dict[str, Any]] = []
    for instrument in midi.instruments:
        program_name = "Drums" if instrument.is_drum else pretty_midi.program_to_instrument_name(
            instrument.program
        )
        for note in instrument.notes:
            normalized = {
                "pitch": int(note.pitch),
                "start": float(note.start),
                "end": float(note.end),
                "velocity": int(note.velocity),
            }
            notes.append(normalized)
            model_events.append(
                {
                    **normalized,
                    "instrument_program": int(instrument.program),
                    "instrument_name": program_name,
                    "is_drum": bool(instrument.is_drum),
                }
            )
    notes.sort(key=lambda note: (note["start"], note["pitch"], note["end"]))
    model_events.sort(
        key=lambda note: (
            note["start"],
            note["instrument_program"],
            note["pitch"],
            note["end"],
        )
    )
    return notes, model_events
