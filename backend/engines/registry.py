"""Engine registry with environment-variable selection.

Production defaults:
  TRANSCRIPTION_ENGINE=basic_pitch
  BEAT_ENGINE=beat_this
  STRUCTURE_ENGINE=allin1
  NOTATION_ENGINE=musescore
  HARMONY_ENGINE=music21
  MELODY_ENGINE=lstom

Keep optional/heavy model engines lazy: importing the registry is part of the API,
analysis, notation, and test paths and must not itself require Torch/TensorFlow.
"""

from __future__ import annotations

import os

from engines.base import (
    BeatTrackingEngine,
    HarmonyEngine,
    MelodyEngine,
    NotationEngine,
    StructureEngine,
    TranscriptionEngine,
)
from engines.beats.librosa_engine import LibrosaBeatEngine
from engines.harmony.music21_engine import Music21HarmonyEngine
from engines.melody.skyline_engine import SkylineMelodyEngine
from engines.notation.musescore_engine import MuseScoreNotationEngine
from engines.structure.allin1_engine import AllInOneEngine


def get_transcription_engine(
    name: str | None = None,
    profile: str | None = None,
    onset_threshold: float = 0.5,
    frame_threshold: float = 0.3,
) -> TranscriptionEngine:
    """Get a transcription engine.

    Args:
        name: Explicit engine name (overrides profile/env).
        profile: Transcription profile: "solo_piano" -> transkun, "general" -> basic_pitch.
                 "auto" retains existing general engine unless trustworthy solo-piano evidence.
        onset_threshold: Onset threshold for engines that support it.
        frame_threshold: Frame threshold for engines that support it.
    """
    # Profile-based routing (only applies when no explicit name given)
    if name is None:
        if profile == "solo_piano":
            name = "transkun"
        elif profile in ("general", "auto", None):
            name = os.environ.get("TRANSCRIPTION_ENGINE", "basic_pitch")
        else:
            raise ValueError(f"Unknown transcription profile: {profile}")

    if name == "basic_pitch":
        try:
            from engines.transcription.basic_pitch import BasicPitchEngine
        except ImportError as exc:
            raise RuntimeError(
                "basic-pitch is not installed. Install the backend worker dependency group."
            ) from exc
        return BasicPitchEngine(
            onset_threshold=onset_threshold,
            frame_threshold=frame_threshold,
        )
    if name == "transkun":
        try:
            from engines.transcription.transkun import TranskunEngine
        except ImportError as exc:
            raise RuntimeError(
                "transkun is not installed. Install the backend worker dependency group."
            ) from exc
        return TranskunEngine(
            onset_threshold=onset_threshold,
            frame_threshold=frame_threshold,
        )
    raise ValueError(f"Unknown transcription engine: {name}")


def get_beat_engine(name: str | None = None) -> BeatTrackingEngine:
    """Resolve the production beat engine.

    Beat This is the default production tracker because localized beat/downbeat
    evidence materially outperformed the legacy librosa path in the repository's
    canonical pulse evaluation. ``BEAT_ENGINE=librosa`` remains an explicit
    operational rollback, not a silent fallback.
    """
    name = name or os.environ.get("BEAT_ENGINE", "beat_this")
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


def get_structure_engine(name: str | None = None) -> StructureEngine:
    name = name or os.environ.get("STRUCTURE_ENGINE", "allin1")
    if name == "allin1":
        return AllInOneEngine()
    raise ValueError(f"Unknown structure engine: {name}")


def get_notation_engine(name: str | None = None) -> NotationEngine:
    """Resolve an explicitly selected score-interpretation path.

    MuseScore remains the default. PM2S is an experimental learned challenger
    under #953: it first derives score MIDI from canonical performance MIDI,
    then the existing MuseScore MIDI-import stage produces MusicXML. Selection
    is explicit; engines never silently catch-and-substitute each other.
    """
    name = name or os.environ.get("NOTATION_ENGINE", "musescore")
    if name == "musescore":
        return MuseScoreNotationEngine()
    if name == "pm2s":
        from engines.notation.pm2s_engine import PM2SNotationEngine

        return PM2SNotationEngine()
    raise ValueError(f"Unknown notation engine: {name}")


def get_harmony_engine(name: str | None = None) -> HarmonyEngine:
    name = name or os.environ.get("HARMONY_ENGINE", "music21")
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
    raise ValueError(f"Unknown harmony engine: {name}")


def get_melody_engine(
    name: str | None = None,
    profile: str | None = None,
) -> MelodyEngine:
    """Get a melody engine.

    Args:
        name: Explicit engine name (overrides profile/env).
        profile: Melody profile:
            "pop" -> lstom (validated), "classical" -> lstom (experimental),
            "auto" -> lstom (default). None uses env var or lstom.
    """
    if name is None:
        if profile == "pop":
            name = "lstom"
        elif profile == "classical":
            # Classical not formally validated; use LStoM with experimental status.
            # Do NOT fall back to skyline — it performs substantially worse.
            name = "lstom"
        elif profile in ("auto", None):
            name = os.environ.get("MELODY_ENGINE", "lstom")
        else:
            raise ValueError(f"Unknown melody profile: {profile}")

    if name == "lstom":
        try:
            from engines.melody.lstom_engine import LStoMMelodyEngine
        except ImportError as exc:
            raise RuntimeError(
                "LStoM's Torch runtime is not installed. Install the backend worker "
                "dependency group."
            ) from exc
        return LStoMMelodyEngine()
    if name == "skyline":
        return SkylineMelodyEngine()
    raise ValueError(f"Unknown melody engine: {name}")


def get_theory_engine(name: str | None = None):
    """Get the theory interpretation engine.

    This engine takes chord timeline + key context and produces
    Roman numerals and harmonic function.
    """
    name = name or os.environ.get("THEORY_ENGINE", "theory_interpreter")
    if name == "theory_interpreter":
        from engines.theory.theory_engine import TheoryEngine

        return TheoryEngine()
    raise ValueError(f"Unknown theory engine: {name}")
