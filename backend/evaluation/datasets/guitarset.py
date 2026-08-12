"""GuitarSet dataset adapter (real guitar transcription).

Source:   https://github.com/marl/GuitarSet
Version:  1.1.0
License:  MIT (as stated in the repository LICENSE)
Split:    test (the repo designates held-out folds)

GuitarSet provides 6-channel audio + JAMS annotations (pitch/beat) for solo
guitar performances. This adapter resolves a single test-split excerpt.
"""

from __future__ import annotations

from typing import Any

from evaluation.datasets import cache
from evaluation.datasets.registry import DatasetAdapter, ManualAcquisitionError, ResolvedClip


class GuitarSetAdapter(DatasetAdapter):
    name = "guitarset"
    license = "MIT"

    def resolve(self, clip: dict[str, Any]) -> ResolvedClip:
        ddir = cache.dataset_dir("guitarset")
        source_id = clip["source_id"]  # e.g. "00_Rock2-142-D_comp"
        audio_rel = clip.get("audio_rel") or f"{source_id}_mic.wav"
        jams_rel = clip.get("jams_rel") or f"{source_id}.jams"
        audio_path = ddir / "audio" / audio_rel
        jams_path = ddir / "annotation" / jams_rel

        missing = [str(p) for p in (audio_path, jams_path) if not p.exists()]
        if missing:
            raise ManualAcquisitionError(
                "GuitarSet requires manual acquisition. Download the test split "
                "and place audio under guitarset/audio/ and JAMS under "
                "guitarset/annotation/. Missing: " + ", ".join(missing)
            )

        return ResolvedClip(
            audio_path=str(audio_path),
            annotations_path=str(jams_path),
        )
