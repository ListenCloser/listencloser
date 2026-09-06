"""Engine registry with typed runtime selection.

Production defaults:
  TRANSCRIPTION_ENGINE=basic_pitch
  BEAT_ENGINE=beat_this
  NOTATION_ENGINE=musescore
  HARMONY_ENGINE=music21
  MELODY_ENGINE=midibert

Keep optional/heavy model engines lazy: importing the registry is part of the API,
analysis, notation, and test paths and must not itself require Torch/TensorFlow.
"""

from __future__ import annotations

from engines.base import (
    BeatTrackingEngine,
    HarmonyEngine,
    MelodyEngine,
    NotationEngine,
    TranscriptionEngine,
)
from engines.beats.librosa_engine import LibrosaBeatEngine
from engines.harmony.music21_engine import Music21HarmonyEngine
from engines.melody.skyline_engine import SkylineMelodyEngine
from engines.notation.musescore_engine import MuseScoreNotationEngine
from settings import EngineSettings


def get_transcription_engine(
    name: str | None = None,
    profile: str | None = None,
    onset_threshold: float = 0.5,
    frame_threshold: float = 0.3,
) -> TranscriptionEngine:
    """Get a transcription engine."""
    if name is None:
        if profile == "solo_piano":
            name = "transkun"
        elif profile in ("general", "auto", None):
            name = EngineSettings().transcription
        else:
            raise ValueError(f"Unknown transcription profile: {profile}")

    if name == "basic_pitch":
        try:
            from engines.transcription.basic_pitch import BasicPitchEngine
        except ImportError as exc:
            raise RuntimeError(
                "basic-pitch is not installed. Install the backend worker dependency group."
            ) from exc
        return BasicPitchEngine(onset_threshold=onset_threshold, frame_threshold=frame_threshold)
    if name == "transkun":
        try:
            from engines.transcription.transkun import TranskunEngine
        except ImportError as exc:
            raise RuntimeError(
                "transkun is not installed. Install the backend worker dependency group."
            ) from exc
        return TranskunEngine(onset_threshold=onset_threshold, frame_threshold=frame_threshold)
    if name == "muscriptor":
        from engines.transcription.muscriptor import MuScriptorEngine

        return MuScriptorEngine()
    raise ValueError(f"Unknown transcription engine: {name}")


def get_beat_engine(name: str | None = None) -> BeatTrackingEngine:
    name = name or EngineSettings().beat
    if name == "librosa":
        return LibrosaBeatEngine()
    if name == "beat_this":
        try:
            from engines.beats.beat_this_engine import BeatThisEngine
        except ImportError as exc:
            raise RuntimeError(
                "beat-this is not installed. Install the backend worker dependency group."
            ) from exc
        return BeatThisEngine()
    raise ValueError(f"Unknown beat engine: {name}")


def get_notation_engine(name: str | None = None) -> NotationEngine:
    name = name or EngineSettings().notation
    if name == "musescore":
        return MuseScoreNotationEngine()
    if name == "pm2s":
        from engines.notation.pm2s_engine import PM2SNotationEngine

        return PM2SNotationEngine()
    raise ValueError(f"Unknown notation engine: {name}")


def get_harmony_engine(name: str | None = None) -> HarmonyEngine:
    name = name or EngineSettings().harmony
    if name == "music21":
        return Music21HarmonyEngine()
    if name == "lv_chordia":
        try:
            from engines.harmony.lv_chordia_engine import LvChordiaHarmonyEngine
        except ImportError as exc:
            raise RuntimeError(
                "lv-chordia is not installed. Install the backend worker dependency group."
            ) from exc
        return LvChordiaHarmonyEngine()
    if name == "chordmini":
        from engines.harmony.chordmini_engine import ChordMiniHarmonyEngine

        return ChordMiniHarmonyEngine()
    raise ValueError(f"Unknown harmony engine: {name}")


def get_melody_engine(
    name: str | None = None,
    profile: str | None = None,
) -> MelodyEngine:
    """Get a symbolic melody-note interpretation engine.

    The default/auto route is MidiBERT-Piano. LStoM remains an explicit
    rollback/evaluation interpretation; no engine silently substitutes another.
    """
    if name is None:
        if profile in ("pop", "classical"):
            name = "midibert"
        elif profile in ("auto", None):
            name = EngineSettings().melody
        else:
            raise ValueError(f"Unknown melody profile: {profile}")

    if name == "midibert":
        from engines.melody.midibert_engine import MidiBERTMelodyEngine

        return MidiBERTMelodyEngine()
    if name == "lstom":
        try:
            from engines.melody.lstom_engine import LStoMMelodyEngine
        except ImportError as exc:
            raise RuntimeError(
                "LStoM's Torch runtime is not installed. Install the backend "
                "worker dependency group."
            ) from exc
        return LStoMMelodyEngine()
    if name == "skyline":
        return SkylineMelodyEngine()
    raise ValueError(f"Unknown melody engine: {name}")


def get_theory_engine(name: str | None = None):
    """Get the theory interpretation engine."""
    name = name or EngineSettings().theory
    if name == "theory_interpreter":
        from engines.theory.theory_engine import TheoryEngine

        return TheoryEngine()
    raise ValueError(f"Unknown theory engine: {name}")
