"""Engine registry with environment-variable selection.

Production defaults:
  TRANSCRIPTION_ENGINE=basic_pitch
  BEAT_ENGINE=librosa
  STRUCTURE_ENGINE=allin1
  NOTATION_ENGINE=music21
"""

from __future__ import annotations

import os

from engines.base import (
    BeatTrackingEngine,
    NotationEngine,
    StructureEngine,
    TranscriptionEngine,
)
from engines.beats.librosa_engine import LibrosaBeatEngine
from engines.notation.music21_engine import Music21NotationEngine
from engines.structure.allin1_engine import AllInOneEngine
from engines.transcription.basic_pitch import BasicPitchEngine


def get_transcription_engine(
    name: str | None = None,
    onset_threshold: float = 0.5,
    frame_threshold: float = 0.3,
) -> TranscriptionEngine:
    name = name or os.environ.get("TRANSCRIPTION_ENGINE", "basic_pitch")
    if name == "basic_pitch":
        return BasicPitchEngine(
            onset_threshold=onset_threshold,
            frame_threshold=frame_threshold,
        )
    raise ValueError(f"Unknown transcription engine: {name}")


def get_beat_engine(name: str | None = None) -> BeatTrackingEngine:
    name = name or os.environ.get("BEAT_ENGINE", "librosa")
    if name == "librosa":
        return LibrosaBeatEngine()
    if name == "beat_this":
        try:
            from engines.beats.beat_this_engine import BeatThisEngine
            return BeatThisEngine()
        except ImportError:
            raise RuntimeError(
                "beat_this is not installed. Install with: pip install beat-this"
            ) from None
    raise ValueError(f"Unknown beat engine: {name}")


def get_structure_engine(name: str | None = None) -> StructureEngine:
    name = name or os.environ.get("STRUCTURE_ENGINE", "allin1")
    if name == "allin1":
        return AllInOneEngine()
    raise ValueError(f"Unknown structure engine: {name}")


def get_notation_engine(name: str | None = None) -> NotationEngine:
    name = name or os.environ.get("NOTATION_ENGINE", "music21")
    if name == "music21":
        return Music21NotationEngine()
    raise ValueError(f"Unknown notation engine: {name}")
