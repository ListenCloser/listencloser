"""Subprocess adapter for heavyweight structure candidates in isolated environments."""

from __future__ import annotations

import json
import os
import shlex
import subprocess
from typing import Any

from .base import StructureAdapter, StructureMetadata, StructureResult


def _segments(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, dict):
        payload = payload.get("segments", payload.get("result", []))
    segments: list[dict[str, Any]] = []
    for raw in payload or []:
        if not isinstance(raw, dict):
            continue
        start = raw.get("start")
        end = raw.get("end")
        if start is None or end is None:
            continue
        start_s = float(start)
        end_s = float(end)
        if start_s < 0 or end_s <= start_s:
            continue
        segments.append(
            {
                "start": start_s,
                "end": end_s,
                "label": str(raw.get("label", "")).strip().lower(),
            }
        )
    return segments


def _csv_env(name: str) -> tuple[str, ...]:
    return tuple(value.strip() for value in os.environ.get(name, "").split(",") if value.strip())


class ExternalJsonStructureAdapter(StructureAdapter):
    """Run an external candidate without importing its dependency graph.

    ``STRUCTURE_EXTERNAL_COMMAND`` is tokenized with ``shlex`` and executed with
    ``shell=False``. Include ``{audio}`` where the audio path belongs; if the
    placeholder is absent, the path is appended. The command must write a JSON
    list of ``{start, end, label?}`` segments (or ``{"segments": [...]}``) to stdout.
    """

    name = "external_json"
    engine = "external_json"

    def __init__(self, device: str = "cpu") -> None:
        super().__init__(device)
        self.command = os.environ.get("STRUCTURE_EXTERNAL_COMMAND", "").strip()
        self.candidate_name = os.environ.get("STRUCTURE_EXTERNAL_NAME", self.name).strip()
        self._argv: list[str] = []

    def load(self) -> None:
        if not self.command:
            raise RuntimeError(
                "STRUCTURE_EXTERNAL_COMMAND is required for external_json evaluation"
            )
        self._argv = shlex.split(self.command)
        if not self._argv:
            raise RuntimeError("STRUCTURE_EXTERNAL_COMMAND parsed to an empty command")
        self._loaded = True

    def analyze(self, audio_path: str) -> StructureResult:
        if not self._loaded:
            self.load()
        argv = [part.replace("{audio}", audio_path) for part in self._argv]
        if all("{audio}" not in part for part in self._argv):
            argv.append(audio_path)
        try:
            completed = subprocess.run(
                argv,
                check=False,
                capture_output=True,
                text=True,
            )
        except OSError as exc:
            return StructureResult(error=f"{type(exc).__name__}: {exc}")
        if completed.returncode != 0:
            stderr = completed.stderr.strip()
            return StructureResult(
                error=f"external candidate exited {completed.returncode}: {stderr[:500]}"
            )
        try:
            payload = json.loads(completed.stdout)
            segments = _segments(payload)
        except (TypeError, ValueError) as exc:
            return StructureResult(error=f"invalid candidate JSON: {exc}")
        if not segments:
            return StructureResult(error="candidate returned no valid segments")
        return StructureResult(segments=segments)

    def metadata(self) -> StructureMetadata:
        return StructureMetadata(
            candidate=self.candidate_name or self.name,
            engine=self.engine,
            code_license=os.environ.get("STRUCTURE_EXTERNAL_CODE_LICENSE") or None,
            checkpoint_license=os.environ.get("STRUCTURE_EXTERNAL_CHECKPOINT_LICENSE") or None,
            upstream_repo=os.environ.get("STRUCTURE_EXTERNAL_REPO") or None,
            upstream_version=os.environ.get("STRUCTURE_EXTERNAL_VERSION") or None,
            checkpoint_name=os.environ.get("STRUCTURE_EXTERNAL_CHECKPOINT") or None,
            training_datasets=_csv_env("STRUCTURE_EXTERNAL_TRAINING_DATASETS"),
            held_out_datasets=_csv_env("STRUCTURE_EXTERNAL_HELD_OUT_DATASETS"),
            training_partition=os.environ.get("STRUCTURE_EXTERNAL_TRAINING_PARTITION") or None,
            held_out_partition=os.environ.get("STRUCTURE_EXTERNAL_HELD_OUT_PARTITION") or None,
            split_source=os.environ.get("STRUCTURE_EXTERNAL_SPLIT_SOURCE") or None,
            notes=os.environ.get("STRUCTURE_EXTERNAL_NOTES", ""),
        )
