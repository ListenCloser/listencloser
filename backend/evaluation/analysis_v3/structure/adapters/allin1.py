"""Optional All-In-One adapter for Structure V1 evaluation."""

from __future__ import annotations

import os
from importlib.metadata import PackageNotFoundError, version
from typing import Any

from .base import StructureAdapter, StructureMetadata, StructureResult


def _normalize_segments(raw_segments: Any) -> list[dict[str, Any]]:
    segments: list[dict[str, Any]] = []
    for raw in raw_segments or []:
        if isinstance(raw, dict):
            start = raw.get("start", raw.get("segment_start"))
            end = raw.get("end", raw.get("segment_end"))
            label = raw.get("label", "")
        else:
            start = getattr(raw, "start", getattr(raw, "segment_start", None))
            end = getattr(raw, "end", getattr(raw, "segment_end", None))
            label = getattr(raw, "label", "")
        if start is None or end is None:
            continue
        start_s = float(start)
        end_s = float(end)
        if start_s < 0 or end_s <= start_s:
            continue
        segments.append(
            {"start": start_s, "end": end_s, "label": str(label).strip().lower()}
        )
    return segments


class AllInOneStructureAdapter(StructureAdapter):
    name = "allin1"
    engine = "allin1"

    def __init__(self, device: str = "cpu") -> None:
        super().__init__(device)
        self.model = os.environ.get("STRUCTURE_ALLIN1_MODEL", "harmonix-all")
        self._module: Any = None

    def load(self) -> None:
        try:
            import allin1  # type: ignore[import-untyped]
        except ImportError as exc:
            raise RuntimeError(
                "All-In-One is not installed. Run this candidate in an isolated research "
                "environment; do not add it to the production backend lock for evaluation."
            ) from exc
        self._module = allin1
        self._loaded = True

    def analyze(self, audio_path: str) -> StructureResult:
        if not self._loaded:
            self.load()
        try:
            raw = self._module.analyze(audio_path, model=self.model, device=self.device)
            segments = _normalize_segments(getattr(raw, "segments", None))
            if not segments:
                return StructureResult(error="candidate returned no valid segments")
            return StructureResult(segments=segments)
        except Exception as exc:
            return StructureResult(error=f"{type(exc).__name__}: {exc}")

    def metadata(self) -> StructureMetadata:
        try:
            package_version = version("allin1")
        except PackageNotFoundError:
            package_version = None
        return StructureMetadata(
            candidate=self.name,
            engine=self.engine,
            code_license="MIT",
            checkpoint_license=None,
            upstream_repo="https://github.com/mir-aidj/all-in-one",
            upstream_version=package_version,
            checkpoint_name=self.model,
            training_datasets=("HarmonixSet",),
            notes=(
                "The harmonix-all checkpoint is an ensemble across HarmonixSet folds. "
                "Do not describe ordinary HarmonixSet evaluation as independent held-out evidence."
            ),
        )
