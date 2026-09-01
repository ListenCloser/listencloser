"""Opt-in Tsumugi instrument-agnostic transcription engine.

Tsumugi is intentionally executed in a separately provisioned Python runtime
instead of being added to the backend worker dependency graph. The adapter
requires an explicit source checkout and local checkpoint and therefore never
relies on Tsumugi's upstream first-run model download. Failures are surfaced to
the caller; this engine never falls back to another transcription system.
"""

from __future__ import annotations

import hashlib
import io
import os
import subprocess
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pretty_midi

from engines.base import EngineProvenance, TranscriptionEngine, TranscriptionResult


class TsumugiEngine(TranscriptionEngine):
    """Run the pinned Tsumugi CLI and normalize its MIDI into engine output."""

    ENGINE = "tsumugi"
    SOURCE_REPOSITORY = "anime-song/tsumugi"
    SOURCE_COMMIT = "9b48501ed05618fee0646c9e267bcb529e957898"
    MODULE = "instrument_agnostic_amt.cli.infer"
    MODULE_PATH = Path("instrument_agnostic_amt/cli/infer.py")

    def __init__(
        self,
        *,
        source_root: str | os.PathLike[str] | None = None,
        python_executable: str | os.PathLike[str] | None = None,
        checkpoint: str | os.PathLike[str] | None = None,
        checkpoint_sha256: str | None = None,
        device: str | None = None,
        timeout_seconds: int | None = None,
        runner: Callable[..., subprocess.CompletedProcess[str]] | None = None,
    ) -> None:
        root_value = source_root or os.environ.get("TSUMUGI_ROOT")
        python_value = python_executable or os.environ.get("TSUMUGI_PYTHON")
        checkpoint_value = checkpoint or os.environ.get("TSUMUGI_CHECKPOINT")
        self._source_root = Path(root_value).expanduser() if root_value else None
        self._python = Path(python_value).expanduser() if python_value else None
        self._checkpoint = Path(checkpoint_value).expanduser() if checkpoint_value else None
        self._checkpoint_sha256 = (
            checkpoint_sha256 or os.environ.get("TSUMUGI_CHECKPOINT_SHA256") or None
        )
        self._device = device or os.environ.get("TSUMUGI_DEVICE", "cpu")
        self._timeout_seconds = (
            timeout_seconds if timeout_seconds is not None else _timeout_from_env()
        )
        if self._timeout_seconds <= 0:
            raise RuntimeError("Tsumugi timeout must be positive")
        self._runner = runner or subprocess.run
        self._checkpoint_verified = False

    @property
    def provenance(self) -> EngineProvenance:
        parameters: dict[str, Any] = {
            "source_repository": self.SOURCE_REPOSITORY,
            "source_commit": self.SOURCE_COMMIT,
            "runtime": "external_python",
            "device": self._device,
            "checkpoint": self._checkpoint.name if self._checkpoint else None,
        }
        if self._checkpoint_sha256:
            parameters["checkpoint_sha256"] = self._checkpoint_sha256.lower()
        return EngineProvenance(
            engine=self.ENGINE,
            library_version=self.SOURCE_COMMIT,
            model="instrument_agnostic_amt/default",
            parameters=parameters,
        )

    def _validate_runtime(self) -> tuple[Path, Path, Path]:
        if self._python is None:
            raise RuntimeError(
                "TSUMUGI_PYTHON must point to the Python executable in a pinned Tsumugi runtime"
            )
        if not self._python.is_file():
            raise RuntimeError(f"Tsumugi Python executable is missing: {self._python}")
        if self._source_root is None:
            raise RuntimeError("TSUMUGI_ROOT must point to the pinned Tsumugi source checkout")
        if not self._source_root.is_dir():
            raise RuntimeError(f"Tsumugi source checkout is missing: {self._source_root}")
        module_path = self._source_root / self.MODULE_PATH
        if not module_path.is_file():
            raise RuntimeError(f"Tsumugi inference module is missing: {module_path}")
        if self._checkpoint is None:
            raise RuntimeError(
                "TSUMUGI_CHECKPOINT must point to an explicitly provisioned Tsumugi checkpoint"
            )
        if not self._checkpoint.is_file():
            raise RuntimeError(f"Tsumugi checkpoint is missing: {self._checkpoint}")
        self._verify_checkpoint()
        return self._source_root, self._python, self._checkpoint

    def _verify_checkpoint(self) -> None:
        if self._checkpoint_verified or not self._checkpoint_sha256 or self._checkpoint is None:
            return
        expected = self._checkpoint_sha256.lower()
        actual = hashlib.sha256()
        with self._checkpoint.open("rb") as fh:
            for chunk in iter(lambda: fh.read(1024 * 1024), b""):
                actual.update(chunk)
        digest = actual.hexdigest()
        if digest != expected:
            raise RuntimeError(
                f"Tsumugi checkpoint SHA256 mismatch: expected {expected}, got {digest}"
            )
        self._checkpoint_verified = True

    def transcribe(
        self, audio_bytes: bytes, fmt: str = "wav", **kwargs: Any
    ) -> TranscriptionResult:
        if not audio_bytes:
            raise ValueError("Tsumugi transcription input must not be empty")
        source_root, python_executable, checkpoint = self._validate_runtime()

        suffix = _audio_suffix(audio_bytes, fmt)
        with tempfile.TemporaryDirectory(prefix="listencloser-tsumugi-") as td:
            root = Path(td)
            audio_path = root / f"input.{suffix}"
            midi_path = root / "output.mid"
            audio_path.write_bytes(audio_bytes)

            command = [
                str(python_executable),
                "-m",
                self.MODULE,
                "--checkpoint",
                str(checkpoint),
                "--audio",
                str(audio_path),
                "--output-midi",
                str(midi_path),
                "--device",
                self._device,
                "--disable-tqdm",
            ]
            try:
                completed = self._runner(
                    command,
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=self._timeout_seconds,
                    cwd=str(source_root),
                )
            except subprocess.TimeoutExpired as exc:
                raise RuntimeError(
                    f"Tsumugi inference exceeded {self._timeout_seconds}s timeout"
                ) from exc
            except OSError as exc:
                raise RuntimeError(f"Tsumugi runtime could not be started: {exc}") from exc

            if completed.returncode != 0:
                detail = (completed.stderr or completed.stdout or "unknown error").strip()
                if len(detail) > 1000:
                    detail = detail[-1000:]
                raise RuntimeError(
                    f"Tsumugi inference failed with exit code {completed.returncode}: {detail}"
                )
            if not midi_path.is_file() or midi_path.stat().st_size == 0:
                raise RuntimeError("Tsumugi inference did not produce MIDI")

            midi_bytes = midi_path.read_bytes()
            if not midi_bytes.startswith(b"MThd"):
                raise RuntimeError("Tsumugi output is not recognizable MIDI")
            try:
                midi_data = pretty_midi.PrettyMIDI(io.BytesIO(midi_bytes))
            except Exception as exc:
                raise RuntimeError(f"Tsumugi produced invalid MIDI: {exc}") from exc

        notes = [
            {
                "pitch": note.pitch,
                "start": note.start,
                "end": note.end,
                "velocity": note.velocity,
            }
            for instrument in midi_data.instruments
            for note in instrument.notes
        ]
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


def _timeout_from_env() -> int:
    raw = os.environ.get("TSUMUGI_TIMEOUT_SECONDS", "900")
    try:
        timeout = int(raw)
    except ValueError as exc:
        raise RuntimeError("TSUMUGI_TIMEOUT_SECONDS must be an integer") from exc
    if timeout <= 0:
        raise RuntimeError("TSUMUGI_TIMEOUT_SECONDS must be positive")
    return timeout


def _audio_suffix(audio_bytes: bytes, fmt: str) -> str:
    if audio_bytes[:4] == b"RIFF":
        return "wav"
    if audio_bytes[:4] == b"OggS":
        return "ogg"
    if audio_bytes[:3] == b"ID3" or audio_bytes[:2] in {b"\xff\xfb", b"\xff\xf3", b"\xff\xf2"}:
        return "mp3"
    if len(audio_bytes) >= 12 and audio_bytes[4:8] == b"ftyp":
        return "m4a"
    normalized = fmt.lower().lstrip(".")
    if not normalized or not normalized.replace("_", "").isalnum():
        raise ValueError(f"Unsupported audio format: {fmt}")
    return normalized