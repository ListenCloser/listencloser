"""Theory interpretation engine for harmonic analysis.

Takes chord timeline + key context and produces:
- Roman numerals
- Harmonic function

Cadence and local-key-region capabilities are intentionally withheld. Their
historical evaluation evidence remains in ``config/capabilities.json``; rejected
implementations do not remain on the production execution path.

This is the production version, not the offline evaluation version.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any

from engines.base import EngineProvenance

logger = logging.getLogger("engines.theory.theory_engine")


@dataclass
class RomanNumeralEvent:
    """A single Roman numeral event."""

    numeral: str
    degree: int
    quality: str
    seventh: bool
    inversion: str | None
    is_secondary: bool
    secondary_target: str | None
    start_seconds: float
    end_seconds: float
    key_context: str
    key_source: str | None = None
    key_provenance: dict[str, Any] | None = None
    chord_source_id: str | None = None
    provenance: dict[str, Any] | None = None


@dataclass
class HarmonicFunctionEvent:
    """A single harmonic function event."""

    function: str  # TONIC, SUBDOMINANT, DOMINANT, AMBIGUOUS
    start_seconds: float
    end_seconds: float
    roman_numeral: str
    key_context: str
    key_source: str | None = None
    key_provenance: dict[str, Any] | None = None
    roman_numeral_source_id: str | None = None
    provenance: dict[str, Any] | None = None


@dataclass
class CadenceEvent:
    """Compatibility shape for the currently withheld cadence capability."""

    type: str
    chords: list[str]
    start_seconds: float
    end_seconds: float
    key_context: str
    confidence: float
    provenance: dict[str, Any] | None = None


@dataclass
class KeyRegionEvent:
    """Compatibility shape for the currently withheld local-key capability."""

    key: str
    start_seconds: float
    end_seconds: float
    confidence: float
    provenance: dict[str, Any] | None = None


@dataclass
class TheoryResult:
    """Result of theory interpretation.

    ``cadences`` and ``key_regions`` remain as compatibility fields while those
    capabilities are withheld. Production always returns them empty; a future
    implementation must earn promotion through evaluation before populating
    either field again.
    """

    roman_numerals: list[RomanNumeralEvent]
    harmonic_functions: list[HarmonicFunctionEvent]
    cadences: list[CadenceEvent]
    key_regions: list[KeyRegionEvent]
    global_key: str | None
    provenance: EngineProvenance


# ── Note/Scale Degree Mapping ─────────────────────────────────────────────

_NOTE_TO_DEGREE = {
    "C": 0,
    "C#": 1,
    "Db": 1,
    "D": 2,
    "D#": 3,
    "Eb": 3,
    "E": 4,
    "F": 5,
    "F#": 6,
    "Gb": 6,
    "G": 7,
    "G#": 8,
    "Ab": 8,
    "A": 9,
    "A#": 10,
    "Bb": 10,
    "B": 11,
}

_DEGREE_TO_NUMERAL_MAJOR = {
    0: "I",
    1: "bII",
    2: "II",
    3: "bIII",
    4: "III",
    5: "IV",
    6: "#IV",
    7: "V",
    8: "bVI",
    9: "VI",
    10: "bVII",
    11: "VII",
}

_DEGREE_TO_NUMERAL_MINOR = {
    0: "i",
    1: "bII",
    2: "ii",
    3: "bIII",
    4: "iii",
    5: "iv",
    6: "#iv",
    7: "v",
    8: "bVI",
    9: "vi",
    10: "bVII",
    11: "vii",
}


def _parse_numeral_parts(numeral: str) -> dict[str, Any]:
    """Parse a Roman numeral string into components."""
    result = {
        "degree": 0,
        "quality": "major",
        "seventh": False,
        "inversion": None,
        "secondary_target": None,
        "altered_root": None,
        "full_numeral": numeral,
    }

    if not numeral:
        return result

    # Handle secondary dominants (V/V, V7/IV, etc.)
    if "/" in numeral:
        parts = numeral.split("/", 1)
        numeral = parts[0]
        result["secondary_target"] = parts[1]

    # Handle altered roots (bVI, #IV, etc.)
    if numeral.startswith("b"):
        result["altered_root"] = "flat"
        numeral = numeral[1:]
    elif numeral.startswith("#"):
        result["altered_root"] = "sharp"
        numeral = numeral[1:]

    # Determine quality from case
    if numeral.isupper():
        result["quality"] = "major"
    elif numeral.islower():
        result["quality"] = "minor"
    else:
        if numeral[0].isupper():
            result["quality"] = "major"
        else:
            result["quality"] = "minor"

    # Extract degree
    simple_numerals = {"I": 1, "II": 2, "III": 3, "IV": 4, "V": 5, "VI": 6, "VII": 7}
    upper_numeral = numeral.upper()
    if upper_numeral in simple_numerals:
        result["degree"] = simple_numerals[upper_numeral]

    # Check for diminished (o) or half-diminished (ø)
    if "o" in numeral.lower():
        result["quality"] = "diminished"
    if "ø" in numeral or "hdim" in numeral.lower():
        result["quality"] = "half-diminished"

    # Check for augmented (+)
    if "+" in numeral:
        result["quality"] = "augmented"

    # Check for seventh
    if "7" in numeral:
        result["seventh"] = True

    return result


def _get_scale_degree(numeral: str) -> int:
    """Extract scale degree from Roman numeral."""
    parts = _parse_numeral_parts(numeral)
    return parts["degree"]


def _get_quality(numeral: str) -> str:
    """Extract chord quality from Roman numeral."""
    parts = _parse_numeral_parts(numeral)
    return parts["quality"]


def _get_inversion(numeral: str) -> str | None:
    """Extract inversion from Roman numeral."""
    if re.search(r"65$", numeral):
        return "first"
    if re.search(r"43$", numeral):
        return "second"
    if re.search(r"42$", numeral) or re.search(r"2$", numeral):
        return "third"
    if re.search(r"6$", numeral) and not re.search(r"6[45]$", numeral):
        return "first"
    return None


def _is_secondary_dominant(numeral: str) -> bool:
    """Check if numeral is a secondary dominant."""
    return "/" in numeral


def _get_secondary_target(numeral: str) -> str | None:
    """Get the target of a secondary dominant."""
    if "/" in numeral:
        return numeral.split("/", 1)[1]
    return None


def _chord_name_to_numeral(chord_name: str, key: str = "C") -> str:
    """Convert a chord name like 'F maj' to a Roman numeral relative to a key.

    This is a purpose-built adapter for lv-chordia's root+quality output.
    music21's ``romanNumeralFromChord`` requires full pitch voicing to
    correctly distinguish dominant-seventh from major-seventh and to detect
    inversions — information that lv-chordia does not provide. The custom
    pitch-class lookup is more accurate for this specific input format and
    avoids a heavy library dependency on the hot path.
    """
    parts = chord_name.split()
    if not parts:
        return ""

    root_name = parts[0]
    quality = parts[1] if len(parts) > 1 else "maj"

    root_idx = _NOTE_TO_DEGREE.get(root_name, 0)
    key_idx = _NOTE_TO_DEGREE.get(key, 0)
    degree = (root_idx - key_idx) % 12

    is_minor = key.endswith("minor") or key.endswith("m")

    if is_minor:
        numeral = _DEGREE_TO_NUMERAL_MINOR.get(degree, f"?{degree}")
    else:
        numeral = _DEGREE_TO_NUMERAL_MAJOR.get(degree, f"?{degree}")

    if quality.startswith("min"):
        numeral = numeral.lower()
    elif quality.startswith("dim"):
        numeral = numeral.lower() + "o"

    if "7" in quality:
        numeral += "7"

    if len(parts) > 2 and "/" in parts[2]:
        inversion = parts[2].split("/")[1]
        numeral += inversion

    return numeral


def _detect_key_from_chords(chords: list[dict[str, Any]]) -> str:
    """Detect key from a sequence of chord names."""
    note_counts = [0] * 12
    for chord in chords:
        root = chord.get("root", "")
        if root in _NOTE_TO_DEGREE:
            note_counts[_NOTE_TO_DEGREE[root]] += 1

    max_count = max(note_counts)
    if max_count == 0:
        return "C"

    tonic_idx = note_counts.index(max_count)
    note_names = list(_NOTE_TO_DEGREE.keys())
    return note_names[tonic_idx]


def _classify_function(numeral: str, key: str | None = None) -> str:
    """Classify harmonic function of a Roman numeral."""
    degree = _get_scale_degree(numeral)
    quality = _get_quality(numeral)

    if degree in (1, 6):
        return "TONIC"
    if degree in (4, 2):
        return "SUBDOMINANT"
    if degree in (5, 7):
        return "DOMINANT"

    if _is_secondary_dominant(numeral):
        return "DOMINANT"

    if degree == 3 and quality == "major":
        return "DOMINANT"
    if degree == 6 and quality == "minor":
        return "TONIC"
    if degree == 2 and quality == "minor":
        return "SUBDOMINANT"

    return "AMBIGUOUS"


class TheoryEngine:
    """Production theory interpretation engine.

    Takes chord timeline + trusted key context and produces Roman numerals and
    harmonic function. Cadence and local-key-region analysis are withheld and
    therefore never executed here.
    """

    ENGINE = "theory_interpreter"

    @property
    def provenance(self) -> EngineProvenance:
        return EngineProvenance(
            engine=self.ENGINE,
            library_version="1.0.0",
            model="deterministic_theory_rules",
        )

    def analyze(
        self,
        chords: list[dict[str, Any]],
        global_key: str | None = None,
        key_source: str | None = None,
        key_provenance: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> TheoryResult:
        """Interpret production-safe theory from a chord timeline.

        Args:
            chords: List of chord events with root/quality or numeral.
            global_key: Trusted key string (e.g. "C major"). When ``None``,
                RN and harmonic-function are WITHHELD — only chords are shown.
            key_source: How the key was detected (e.g. "music21_independent").
            key_provenance: Provenance dict for the key detection.

        Returns:
            TheoryResult with Roman numerals and harmonic functions. Cadences
            and local key regions stay empty while those capabilities remain
            withheld by the capability registry.
        """
        roman_numerals = []
        harmonic_functions = []

        if not chords:
            return TheoryResult(
                roman_numerals=roman_numerals,
                harmonic_functions=harmonic_functions,
                cadences=[],
                key_regions=[],
                global_key=global_key,
                provenance=self.provenance,
            )

        # No trusted key → withhold RN and harmonic function.
        # Chords are still produced by the caller (lv-chordia); only the
        # theory interpretation is suppressed.
        if not global_key:
            logger.info(
                "theory_withheld_no_key",
                extra={"chord_count": len(chords)},
            )
            return TheoryResult(
                roman_numerals=[],
                harmonic_functions=[],
                cadences=[],
                key_regions=[],
                global_key=None,
                provenance=self.provenance,
            )

        key_name = global_key.split()[0] if global_key else "C"

        # Process each chord
        for chord in chords:
            start = chord.get("start", 0)
            end = chord.get("end", 0)

            # Convert to Roman numeral
            if chord.get("numeral") and not chord.get("root"):
                numeral = chord["numeral"]
            elif chord.get("root") and chord.get("quality"):
                numeral = _chord_name_to_numeral(f"{chord['root']} {chord['quality']}", key_name)
            else:
                continue

            if not numeral:
                continue

            rn_event = RomanNumeralEvent(
                numeral=numeral,
                degree=_get_scale_degree(numeral),
                quality=_get_quality(numeral),
                seventh="7" in numeral,
                inversion=_get_inversion(numeral),
                is_secondary=_is_secondary_dominant(numeral),
                secondary_target=_get_secondary_target(numeral),
                start_seconds=start,
                end_seconds=end,
                key_context=global_key,
                key_source=key_source,
                key_provenance=key_provenance,
                chord_source_id=chord.get("id"),
                provenance=self.provenance.to_dict(),
            )
            roman_numerals.append(rn_event)

            function = _classify_function(numeral, global_key)
            harmonic_functions.append(
                HarmonicFunctionEvent(
                    function=function,
                    start_seconds=start,
                    end_seconds=end,
                    roman_numeral=numeral,
                    key_context=global_key,
                    key_source=key_source,
                    key_provenance=key_provenance,
                    roman_numeral_source_id=str(len(roman_numerals) - 1),
                    provenance=self.provenance.to_dict(),
                )
            )

        # These compatibility arrays are intentionally empty. The capability
        # registry records the failed evaluations that caused both features to
        # be withheld; re-populating either requires a separately evaluated and
        # promoted implementation.
        return TheoryResult(
            roman_numerals=roman_numerals,
            harmonic_functions=harmonic_functions,
            cadences=[],
            key_regions=[],
            global_key=global_key,
            provenance=self.provenance,
        )
