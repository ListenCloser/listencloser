"""Music21 symbolic harmony engine.

Wraps music21-based harmonic analysis (key, chords, Roman numerals,
voice leading, phrases) behind the HarmonyEngine seam. Cadence detection is
explicitly withheld until a validated detector earns production eligibility.
"""

from __future__ import annotations

import logging
import os
import tempfile
from typing import Any

from engines.base import EngineProvenance, HarmonyEngine, HarmonyResult

logger = logging.getLogger("engines.harmony.music21")

_NOTES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

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


def _m21_key(score):
    """Delegate key estimation to music21's built-in analysis.

    Returns ``None`` when there is no reliable evidence (a parse failure, a
    missing tonic, or a missing correlation coefficient) rather than
    fabricating a "C major" default or a made-up confidence value.
    """
    try:
        key = score.analyze("key")
        corr = key.correlationCoefficient
        if corr is None:
            return None
        tonic = key.tonic.name if key.tonic else None
        if tonic is None:
            return None
        return {
            "tonic": tonic,
            "mode": key.mode or "major",
            "confidence": round(float(corr), 3),
        }
    except Exception:
        logger.warning("music21 key estimation failed", exc_info=True)
        return None


def _m21_chords(score) -> list[dict[str, Any]]:
    """Delegate chord detection to music21's chord analysis.

    Chords whose root or quality cannot be determined are skipped so the
    surface does not fill with ``?:unknown`` spam.
    """
    results: list[dict[str, Any]] = []
    try:
        for chord in score.flatten().getElementsByClass("Chord"):
            try:
                root = chord.root()
                if root is None:
                    continue
                root_name = root.name
                implied = str(chord.quality) if hasattr(chord, "quality") else ""
                quality = _QUALITY_MAP.get(implied, implied)
                if not quality or quality == "unknown":
                    continue
                start = float(chord.getOffsetInHierarchy(score))
                dur = float(chord.quarterLength) if hasattr(chord, "quarterLength") else 0.0
                if dur > 0:
                    results.append(
                        {
                            "root": root_name,
                            "quality": quality,
                            "start": round(start, 3),
                            "end": round(start + dur, 3),
                        }
                    )
            except Exception:
                continue
    except Exception:
        pass
    return results


def _m21_roman_numerals(score, detected_key) -> list[dict[str, Any]]:
    """Delegate Roman numeral analysis to music21."""
    try:
        from music21 import roman
    except ImportError:
        return []
    results: list[dict[str, Any]] = []
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
                    implied = str(rn.impliedQuality) if hasattr(rn, "impliedQuality") else "unknown"
                    quality = _QUALITY_MAP.get(implied, implied)
                    if not quality or quality == "unknown":
                        continue
                    start = float(ch.getOffsetInHierarchy(score))
                    dur = float(ch.quarterLength) if hasattr(ch, "quarterLength") else 0.0
                    results.append(
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
            if len(results) > 500:
                break
        if len(results) > 500:
            break
    return results


def _m21_voice_leading(score):
    """Voice-leading analysis, only when separated voices exist.

    Transcribed MIDI is typically a single flattened part or an arbitrary
    parser split. Contrapuntal motion statistics are meaningless without
    trustworthy independent voices, so suppress when fewer than two parts
    carry independent melodic lines.
    """
    try:
        from music21 import voiceLeading
    except ImportError:
        return None
    parts = [p for p in list(score.parts) if _has_melodic_content(p)]
    if len(parts) < 2:
        return None
    parallel = contrary = oblique = similar = total = 0
    for i in range(min(len(parts), 4)):
        for j in range(i + 1, min(len(parts), 4)):
            try:
                for vlq in voiceLeading.iterateAllVoiceLeadingQuartets(parts[i], parts[j]):
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
    if total == 0:
        return None
    p, c, o, s = (round(n / total, 3) for n in [parallel, contrary, oblique, similar])
    dominant = max(
        ("parallel", p),
        ("contrary", c),
        ("oblique", o),
        ("similar", s),
        key=lambda x: x[1],
    )
    return {
        "parallel": p,
        "contrary": c,
        "oblique": o,
        "similar": s,
        "motion_summary": f"{dominant[0]} motion dominates ({dominant[1] * 100:.0f}%)",
    }


def _has_melodic_content(part) -> bool:
    """A part has melodic content if it contains enough notes to form a line."""
    try:
        notes = list(part.recurse().getElementsByClass("Note"))
        return len(notes) >= 4
    except Exception:
        return False


def _m21_phrases(score) -> list[dict[str, Any]]:
    """Phrase boundary detection is NOT implemented.

    The previous implementation returned chord spans labelled as "phrases",
    which is misleading. Real phrase-boundary analysis requires evidence
    (rests, slurs, cadence context, melodic closure) that is not available
    from raw transcription. Return empty to avoid fake phrase claims.
    """
    return []


class Music21HarmonyEngine(HarmonyEngine):
    ENGINE = "music21"

    def __init__(self) -> None:
        pass

    @property
    def provenance(self) -> EngineProvenance:
        return EngineProvenance(
            engine=self.ENGINE,
            library_version=_music21_version(),
        )

    def component_provenance(self) -> dict[str, EngineProvenance]:
        """Per-sub-capability provenance.

        Music21 delivers key, chords, Roman numerals, and voice leading via its
        own modules. Cadence and phrase outputs are deliberately unavailable;
        their entries record abstention rather than attributing a custom detector
        that does not meet the evidence bar.
        """
        music21 = EngineProvenance(engine="music21", library_version=_music21_version())
        unavailable = EngineProvenance(
            engine="unavailable",
            library_version="n/a",
            parameters={"status": "withheld", "returns_empty": True},
        )
        return {
            "key": music21,
            "chords": music21,
            "roman_numerals": music21,
            "cadences": unavailable,
            "voice_leading": music21,
            "phrases": unavailable,
        }

    def analyze(
        self,
        midi_bytes: bytes,
        tempo_bpm: float | None = None,
        audio_bytes: bytes | None = None,
        **kwargs: Any,
    ) -> HarmonyResult:
        """Symbolic harmonic analysis of a MIDI file.

        audio_bytes is accepted but ignored - music21 is a symbolic engine.
        """
        from music21 import converter

        components = self.component_provenance()

        score = None
        with tempfile.TemporaryDirectory() as td:
            in_path = os.path.join(td, "input.mid")
            with open(in_path, "wb") as f:
                f.write(midi_bytes)
            try:
                score = converter.parse(in_path, quantizePost=False)
            except Exception:
                logger.exception("music21 parse failed")

        if score is None:
            return HarmonyResult(
                key=None,
                chords=[],
                roman_numerals=[],
                cadences=[],
                voice_leading=None,
                phrases=[],
                provenance=self.provenance,
                component_provenance=components,
            )

        key_result = _m21_key(score)
        detected_key = score.analyze("key")
        return HarmonyResult(
            key=key_result,
            chords=_m21_chords(score),
            roman_numerals=_m21_roman_numerals(score, detected_key),
            cadences=[],
            voice_leading=_m21_voice_leading(score),
            phrases=_m21_phrases(score),
            provenance=self.provenance,
            component_provenance=components,
        )


def _music21_version() -> str:
    try:
        import music21

        return music21.__version__  # type: ignore[attr-defined]
    except Exception:
        return "unknown"
