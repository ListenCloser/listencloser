"""MuseScore Studio notation engine.

This adapter deliberately treats MuseScore as an external performance-MIDI to
readable-score system.  It does not rewrite the canonical performance MIDI used
by Piano Roll.  MuseScore's imported/normalized MIDI and MusicXML are derived
notation artifacts.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from engines.base import EngineProvenance, NotationResult


class MuseScoreNotationEngine:
    """Convert performance MIDI to readable notation through MuseScore Studio.

    MuseScore currently performs its own MIDI-import interpretation.  The
    ListenCloser beat/downbeat grid is therefore recorded as available input but
    is *not* claimed as consumed by this candidate.  A beat-conditioned learned
    quantizer can replace this adapter later without changing the product-facing
    NotationEngine contract.
    """

    ENGINE = "musescore"
    DEFAULT_TIMEOUT_SECONDS = 120.0
    _EXECUTABLE_CANDIDATES = (
        "MuseScore4",
        "mscore4",
        "musescore4",
        "MuseScore",
        "mscore",
        "musescore",
    )

    def __init__(
        self,
        executable: str | None = None,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        self._executable = executable
        self._timeout_seconds = timeout_seconds
        self._resolved_executable: str | None = None
        self._version: str | None = None

    @property
    def provenance(self) -> EngineProvenance:
        executable = self._resolve_executable()
        return EngineProvenance(
            engine=self.ENGINE,
            library_version=self._get_version(executable),
            parameters={
                "interface": "cli_batch_conversion",
                "headless": True,
                "midi_import_owner": "musescore",
                "beat_grid_consumed": False,
            },
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
        """Import performance MIDI in MuseScore and export MIDI + MusicXML.

        ``beat_times``/``downbeats``/``beat_positions`` are intentionally not
        injected into MuseScore's importer in this first candidate.  Returning
        that limitation in ``quantization_report`` keeps the comparison honest
        and makes a later Beat-This-conditioned candidate directly measurable.
        """
        if not midi_bytes.startswith(b"MThd"):
            raise ValueError("MuseScore notation input must be a MIDI file")

        executable = self._resolve_executable()

        with tempfile.TemporaryDirectory(prefix="listencloser-musescore-") as td:
            root = Path(td)
            input_midi = root / "performance.mid"
            output_xml = root / "score.musicxml"
            output_midi = root / "notation.mid"
            job_file = root / "job.json"

            input_midi.write_bytes(midi_bytes)
            job_file.write_text(
                json.dumps(
                    [
                        {
                            "in": str(input_midi),
                            "out": [str(output_xml), str(output_midi)],
                        }
                    ]
                ),
                encoding="utf-8",
            )

            completed = self._run(
                [executable, "--job", str(job_file)],
                env=self._isolated_environment(root),
            )
            if completed.returncode != 0:
                detail = (completed.stderr or completed.stdout or "unknown error").strip()
                raise RuntimeError(
                    f"MuseScore conversion failed with exit {completed.returncode}: "
                    f"{detail[:500]}"
                )

            if not output_xml.is_file() or output_xml.stat().st_size == 0:
                raise RuntimeError("MuseScore conversion did not produce MusicXML")
            if not output_midi.is_file() or output_midi.stat().st_size == 0:
                raise RuntimeError("MuseScore conversion did not produce notation MIDI")

            musicxml = output_xml.read_bytes()
            notation_midi = output_midi.read_bytes()

        if b"<score-partwise" not in musicxml and b"<score-timewise" not in musicxml:
            raise RuntimeError("MuseScore output is not recognizable MusicXML")
        if not notation_midi.startswith(b"MThd"):
            raise RuntimeError("MuseScore output is not recognizable MIDI")

        return NotationResult(
            notation_midi=notation_midi,
            musicxml=musicxml,
            quantization_report={
                "engine": self.ENGINE,
                "input": "performance_midi",
                "midi_import_owner": "musescore",
                "beat_grid_available": bool(beat_times),
                "beat_grid_consumed": False,
                "beat_count": len(beat_times),
                "downbeat_count": len(downbeats) if downbeats is not None else None,
                "beat_positions_available": beat_positions is not None,
                "adaptive_requested": adaptive,
                "notation_ready_requested": notation_ready,
                "piano_grand_staff_requested": piano_grand_staff,
            },
            provenance=self.provenance,
        )

    def _resolve_executable(self) -> str:
        if self._resolved_executable is not None:
            return self._resolved_executable

        configured = self._executable or os.environ.get("MUSESCORE_BIN")
        if configured:
            self._resolved_executable = configured
            return configured

        for candidate in self._EXECUTABLE_CANDIDATES:
            found = shutil.which(candidate)
            if found:
                self._resolved_executable = found
                return found

        raise RuntimeError(
            "MuseScore executable not found. Install MuseScore Studio 4 and set "
            "MUSESCORE_BIN to the executable/AppImage path."
        )

    def _get_version(self, executable: str) -> str:
        if self._version is not None:
            return self._version

        completed = self._run([executable, "--version"], env=os.environ.copy())
        if completed.returncode != 0:
            detail = (completed.stderr or completed.stdout or "unknown error").strip()
            raise RuntimeError(
                f"MuseScore version probe failed with exit {completed.returncode}: "
                f"{detail[:500]}"
            )

        version_text = (completed.stdout or completed.stderr or "").strip()
        if not version_text:
            raise RuntimeError("MuseScore version probe returned no version")
        self._version = version_text
        return version_text

    def _run(self, args: list[str], *, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
        try:
            return subprocess.run(
                args,
                check=False,
                capture_output=True,
                text=True,
                timeout=self._timeout_seconds,
                env=env,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise RuntimeError(f"MuseScore command failed: {exc}") from exc

    @staticmethod
    def _isolated_environment(root: Path) -> dict[str, str]:
        """Give each conversion isolated preferences/cache and force headless Qt."""
        env = os.environ.copy()
        env.update(
            {
                "QT_QPA_PLATFORM": "offscreen",
                "SKIP_LIBJACK": "1",
                "XDG_CONFIG_HOME": str(root / "config"),
                "XDG_DATA_HOME": str(root / "data"),
                "XDG_CACHE_HOME": str(root / "cache"),
            }
        )
        return env
