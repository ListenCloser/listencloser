"""Beat This! beat/downbeat tracking engine (experimental).

Installed optionally behind the BeatTrackingEngine interface.
Fails explicitly when beat_this is not installed; does not silently fall back.
"""

from __future__ import annotations

import os
import tempfile
from typing import Any

from engines.base import BeatTrackingEngine, BeatTrackingResult, EngineProvenance


class BeatThisEngine(BeatTrackingEngine):
    ENGINE = "beat_this"

    def __init__(self) -> None:
        pass

    @property
    def provenance(self) -> EngineProvenance:
        return EngineProvenance(
            engine=self.ENGINE,
            library_version=_beat_this_version(),
        )

    def analyze(self, wav_bytes: bytes, **kwargs: Any) -> BeatTrackingResult:
        import beat_this  # type: ignore[import-untyped]

        tmp_path: str | None = None
        try:
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                f.write(wav_bytes)
                f.flush()
                tmp_path = f.name
            result = beat_this.run(tmp_path)
        finally:
            if tmp_path and os.path.exists(tmp_path):
                os.unlink(tmp_path)

        downbeats_raw = result.get("downbeats", [])
        return BeatTrackingResult(
            bpm=float(result.get("bpm", 0)),
            beats=[float(b) for b in result.get("beats", [])],
            downbeats=[float(d) for d in downbeats_raw] if downbeats_raw else None,
            beat_positions=None,
            provenance=self.provenance,
        )


def _beat_this_version() -> str:
    try:
        from importlib.metadata import version

        return version("beat_this")
    except Exception:
        return "unknown"
