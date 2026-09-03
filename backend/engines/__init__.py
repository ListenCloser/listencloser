"""Pluggable music inference engines.

Each engine is an internal abstraction that wraps a specific ML/MIR library.
The production defaults are:
  - transcription: basic_pitch
  - beat tracking: librosa
  - notation: music21
  - harmony: music21
  - melody: skyline (pretty_midi + custom heuristic)

Usage:
  from engines.registry import get_transcription_engine
  engine = get_transcription_engine("basic_pitch")
  result = engine.transcribe(audio_bytes)
"""

from engines.registry import (
    get_beat_engine,
    get_harmony_engine,
    get_melody_engine,
    get_notation_engine,
    get_transcription_engine,
)

__all__ = [
    "get_transcription_engine",
    "get_beat_engine",
    "get_notation_engine",
    "get_harmony_engine",
    "get_melody_engine",
]
