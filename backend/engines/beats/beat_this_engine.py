"""Beat This! beat/downbeat tracking engine (experimental).

Installed optionally behind the BeatTrackingEngine interface.
When unavailable, the registry falls back to librosa.
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
        try:
            import beat_this  # type: ignore[import-untyped]
        except ImportError:
            raise RuntimeError("beat_this is not installed")

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            f.write(wav_bytes)
            f.flush()
            result = beat_this.run(f.name)
        os.unlink(f.name)

        bpm = float(result.get("bpm", 0))
        beats = [float(b) for b in result.get("beats", [])]
        downbeats = [float(d) for d in result.get("downbeats", [])]
        bp = result.get("beat_positions")
        beat_positions = [int(p) for p in bp] if bp else list(range(len(beats)))
        return BeatTrackingResult(
            bpm=bpm,
            beats=beats,
            downbeats=downbeats if downbeats else None,
            beat_positions=beat_positions,
            provenance=self.provenance,
        )


def _beat_this_version() -> str:
    try:
        from importlib.metadata import version

        return version("beat_this")
    except Exception:
        return "unknown"
