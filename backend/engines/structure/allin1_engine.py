"""All-In-One structure analysis engine (optional)."""

from __future__ import annotations

import os
from typing import Any

from engines.base import EngineProvenance, StructureEngine, StructureResult


def _segment_values(seg: Any) -> dict[str, Any]:
    """Normalize an allin1 segment (attributed object or dict) to a plain dict."""
    if isinstance(seg, dict):
        return {
            "start": seg.get("start", seg.get("segment_start", 0)),
            "end": seg.get("end", seg.get("segment_end", 0)),
            "label": seg.get("label", ""),
        }
    return {
        "start": getattr(seg, "start", getattr(seg, "segment_start", 0)),
        "end": getattr(seg, "end", getattr(seg, "segment_end", 0)),
        "label": getattr(seg, "label", ""),
    }


class AllInOneEngine(StructureEngine):
    ENGINE = "allin1"

    def __init__(self, model: str | None = None) -> None:
        self._model = model or os.environ.get("ALLIN1_MODEL", "harmonix-all")
        self._enabled = os.environ.get("ALLIN1_ENABLED", "false").lower() in {"1", "true", "yes"}

    @property
    def provenance(self) -> EngineProvenance:
        return EngineProvenance(
            engine=self.ENGINE,
            library_version=_allin1_version(),
            model=self._model,
            parameters={"device": os.environ.get("ALLIN1_DEVICE", "cpu")},
        )

    def analyze(self, wav_bytes: bytes | str, **kwargs: Any) -> StructureResult | None:
        if not self._enabled:
            return None

        try:
            import allin1  # type: ignore[import-untyped]

            if isinstance(wav_bytes, str):
                result = allin1.analyze(
                    wav_bytes, model=self._model, device=os.environ.get("ALLIN1_DEVICE", "cpu")
                )
            else:
                result = allin1.analyze(wav_bytes)
            if result is None:
                return None
            segments = [
                {
                    "start": round(float(v["start"]), 3),
                    "end": round(float(v["end"]), 3),
                    "label": str(v["label"]).strip().lower() or "section",
                }
                for v in (_segment_values(s) for s in (getattr(result, "segments", None) or []))
                if float(v["end"]) > float(v["start"]) >= 0
            ]
            beats = [round(float(b), 3) for b in getattr(result, "beats", [])]
            downbeats = [round(float(d), 3) for d in getattr(result, "downbeats", [])] or None
            bpm = round(float(getattr(result, "bpm", 0)), 2)
            if bpm <= 0 or not beats:
                return None
            return StructureResult(
                bpm=bpm,
                beats=beats,
                downbeats=downbeats,
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
