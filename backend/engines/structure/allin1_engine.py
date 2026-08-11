"""All-In-One structure analysis engine (optional)."""

from __future__ import annotations

import os
from typing import Any

from engines.base import EngineProvenance, StructureEngine, StructureResult


class AllInOneEngine(StructureEngine):
    ENGINE = "allin1"

    def __init__(self) -> None:
        self._model = os.environ.get("ALLIN1_MODEL", "harmonix-all")
        self._enabled = os.environ.get("ALLIN1_ENABLED", "false") == "true"

    @property
    def provenance(self) -> EngineProvenance:
        return EngineProvenance(
            engine=self.ENGINE,
            library_version=_allin1_version(),
            model=self._model,
            parameters={"device": os.environ.get("ALLIN1_DEVICE", "cpu")},
        )

    def analyze(self, wav_bytes: bytes, **kwargs: Any) -> StructureResult | None:
        if not self._enabled:
            return None

        try:
            import allin1  # type: ignore[import-untyped]

            result = allin1.analyze(wav_bytes)
            if result is None:
                return None
            segments = [
                {
                    "start": float(getattr(s, "start", getattr(s, "segment_start", 0))),
                    "end": float(getattr(s, "end", getattr(s, "segment_end", 0))),
                    "label": str(getattr(s, "label", "")),
                }
                for s in getattr(result, "segments", [])
            ]
            return StructureResult(
                bpm=float(getattr(result, "bpm", 0)),
                beats=[float(b) for b in getattr(result, "beats", [])],
                downbeats=[float(d) for d in getattr(result, "downbeats", [])] or None,
                beat_positions=[int(p) for p in getattr(result, "beat_positions", [])],
                segments=segments,
                provenance=self.provenance,
            )
        except ImportError:
            return None


def _allin1_version() -> str:
    try:
        from importlib.metadata import version

        return version("allin1")
    except Exception:
        return "unknown"
