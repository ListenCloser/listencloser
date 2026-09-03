"""Harmony engine adapters for OSS evaluation.

Adapters for:
- Music21 symbolic (existing baseline)

The former lv-chordia adapter was removed: `chordia` is not on PyPI and its
repository no longer resolves, so it could never run (see
`evaluation/reports/harmony_feasibility.md`).

Cadence analysis is intentionally absent here. The adjacent-Roman-numeral
heuristic previously duplicated in this adapter was rejected and must not be
reintroduced as benchmark evidence.
"""

from __future__ import annotations

import logging
import os
import tempfile
from dataclasses import dataclass
from typing import Any

from evaluation.engines import EngineAdapter, EngineInfo

logger = logging.getLogger("eval.engines.harmony")


# ============================================================
# Music21 Symbolic (existing baseline - already in production)
# ============================================================


@dataclass
class Music21HarmonyAdapter(EngineAdapter):
    engine_info = EngineInfo(
        name="music21_symbolic",
        category="harmony",
        repo_url="https://github.com/cuthbertLab/music21",
        license="BSD",
        install_cmd="pip install music21",
        model_size_mb=0,
        requires_gpu=False,
        notes=(
            "Evaluation-only symbolic baseline for key, chords, RN, and voice "
            "leading. Cadence is withheld pending validated evidence."
        ),
    )

    def __init__(self, **kwargs):
        pass

    def is_available(self) -> bool:
        try:
            import music21  # noqa: F401

            return True
        except Exception:
            return False

    def prepare(self) -> None:
        pass

    def analyze_harmony(self, midi_bytes: bytes, **kwargs) -> dict[str, Any]:
        from music21 import converter, roman, voiceLeading

        # Write MIDI to temp file for music21 parsing (BytesIO triggers
        # MuseData format detection bug in music21)
        with tempfile.NamedTemporaryFile(suffix=".mid", delete=False) as f:
            f.write(midi_bytes)
            temp_path = f.name

        try:
            score = converter.parse(temp_path)
        finally:
            os.unlink(temp_path)

        # Key estimation
        k = score.analyze("key")
        key_result = {
            "tonic": k.tonic.name if k.tonic else "C",
            "mode": k.mode or "major",
            "confidence": float(k.correlationCoefficient) if k.correlationCoefficient else 0.0,
        }

        # Chords
        chords = []
        for ch in score.flatten().getElementsByClass("Chord"):
            try:
                root = ch.root()
                if root is None:
                    continue
                root_name = root.name
                implied = str(ch.quality) if hasattr(ch, "quality") else ""
                quality = _quality_map(implied)
                if not quality or quality == "unknown":
                    continue
                start = float(ch.getOffsetInHierarchy(score))
                dur = float(ch.quarterLength) if hasattr(ch, "quarterLength") else 0.0
                if dur > 0:
                    chords.append(
                        {
                            "root": root_name,
                            "quality": quality,
                            "start": round(start, 3),
                            "end": round(start + dur, 3),
                        }
                    )
            except Exception:
                continue

        # Roman numerals
        roman_numerals = []
        detected_key = score.analyze("key")
        for part in score.parts:
            for measure in part.getElementsByClass("Measure"):
                for ch in measure.getElementsByClass("Chord"):
                    try:
                        rn = roman.romanNumeralFromChord(ch, detected_key)
                        if not rn.figure:
                            continue
                        root_p = ch.root()
                        if root_p is None:
                            continue
                        root_name = root_p.name
                        implied = (
                            str(rn.impliedQuality) if hasattr(rn, "impliedQuality") else "unknown"
                        )
                        quality = _quality_map(implied)
                        if not quality or quality == "unknown":
                            continue
                        start = float(ch.getOffsetInHierarchy(score))
                        dur = float(ch.quarterLength) if hasattr(ch, "quarterLength") else 0.0
                        roman_numerals.append(
                            {
                                "figure": rn.figure,
                                "root": root_name,
                                "quality": quality,
                                "start": round(start, 3),
                                "end": round(start + dur, 3),
                            }
                        )
                    except Exception:
                        continue

        # Cadence is deliberately withheld. A chord progression such as V-I is
        # not sufficient evidence of phrase closure, and evaluation code must
        # not revive the rejected adjacent-RN heuristic as a benchmark result.
        cadences: list[dict[str, Any]] = []

        # Voice leading
        voice_leading = None
        try:
            parts = [p for p in list(score.parts) if _has_melodic_content(p)]
            if len(parts) >= 2:
                parallel = contrary = oblique = similar = total = 0
                for i in range(min(len(parts), 4)):
                    for j in range(i + 1, min(len(parts), 4)):
                        try:
                            for vlq in voiceLeading.iterateAllVoiceLeadingQuartets(
                                parts[i], parts[j]
                            ):
                                motion = vlq.motionType()
                                if "Parallel" in str(motion):
                                    parallel += 1
                                elif "Contrary" in str(motion):
                                    contrary += 1
                                elif "Oblique" in str(motion):
                                    oblique += 1
                                elif "Similar" in str(motion):
                                    similar += 1
                                total += 1
                                if total > 2000:
                                    break
                        except Exception:
                            continue
                        if total > 2000:
                            break
                    if total > 2000:
                        break
                if total > 0:
                    p, c, o, s = (
                        round(n / total, 3) for n in [parallel, contrary, oblique, similar]
                    )
                    dominant = max(
                        ("parallel", p),
                        ("contrary", c),
                        ("oblique", o),
                        ("similar", s),
                        key=lambda x: x[1],
                    )
                    voice_leading = {
                        "parallel": p,
                        "contrary": c,
                        "oblique": o,
                        "similar": s,
                        "motion_summary": (
                            f"{dominant[0]} motion dominates ({dominant[1] * 100:.0f}%)"
                        ),
                    }
        except Exception:
            pass

        return {
            "key": key_result,
            "chords": chords,
            "roman_numerals": roman_numerals,
            "cadences": cadences,
            "voice_leading": voice_leading,
            "phrases": [],  # Not implemented
        }

    def transcribe(self, audio_bytes: bytes, **kwargs) -> dict[str, Any]:
        raise NotImplementedError

    def estimate_beats(self, audio_bytes: bytes, **kwargs) -> dict[str, Any]:
        raise NotImplementedError

    def analyze_structure(self, audio_bytes: bytes, **kwargs) -> dict[str, Any]:
        raise NotImplementedError


# ============================================================
# Helpers
# ============================================================

_QUALITY_MAP = {
    "major": "M",
    "minor": "m",
    "diminished": "dim",
    "augmented": "aug",
    "dominant seventh": "7",
    "major seventh": "maj7",
    "minor seventh": "min7",
    "half-diminished": "m7b5",
    "diminished seventh": "dim7",
    "suspended fourth": "sus4",
    "major sixth": "6",
    "minor sixth": "m6",
    "dominant ninth": "9",
}


def _quality_map(implied: str) -> str:
    return _QUALITY_MAP.get(implied, implied)


def _has_melodic_content(part) -> bool:
    try:
        notes = list(part.recurse().getElementsByClass("Note"))
        return len(notes) >= 4
    except Exception:
        return False


# ============================================================
# Registry
# ============================================================

HARMONY_ADAPTERS = {
    "music21_symbolic": Music21HarmonyAdapter,
}


def get_harmony_adapter(name: str, **kwargs) -> EngineAdapter:
    if name not in HARMONY_ADAPTERS:
        raise ValueError(f"Unknown harmony adapter: {name}. Available: {list(HARMONY_ADAPTERS)}")
    return HARMONY_ADAPTERS[name](**kwargs)


def list_harmony_adapters() -> list[str]:
    return list(HARMONY_ADAPTERS.keys())
