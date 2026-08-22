"""Theory interpretation engine for harmonic analysis.

Takes chord timeline + key context and produces:
- Roman numerals
- Harmonic function

This is the production version, not the offline evaluation version.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from engines.base import EngineProvenance


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
    roman_numeral_source_id: str | None = None
    provenance: dict[str, Any] | None = None


@dataclass
class CadenceEvent:
    """A single cadence event."""

    type: str  # PAC, IAC, HC, PC, DC
    chords: list[str]  # [chord_before, chord_after]
    start_seconds: float
    end_seconds: float
    key_context: str
    confidence: float
    provenance: dict[str, Any] | None = None


@dataclass
class KeyRegionEvent:
    """A detected key region."""

    key: str
    start_seconds: float
    end_seconds: float
    confidence: float
    provenance: dict[str, Any] | None = None


@dataclass
class TheoryResult:
    """Result of theory interpretation."""

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
    """Convert a chord name like 'F maj' to a Roman numeral relative to a key."""
    parts = chord_name.split()
    if not parts:
        return ""

    root_name = parts[0]
    quality = parts[1] if len(parts) > 1 else "maj"

    root_idx = _NOTE_TO_DEGREE.get(root_name, 0)
    key_idx = _NOTE_TO_DEGREE.get(key, 0)
    degree = (root_idx - key_idx) % 12

    # Determine if key is minor
    is_minor = key.endswith("minor") or key.endswith("m")

    if is_minor:
        numeral = _DEGREE_TO_NUMERAL_MINOR.get(degree, f"?{degree}")
    else:
        numeral = _DEGREE_TO_NUMERAL_MAJOR.get(degree, f"?{degree}")

    # Handle quality
    if quality.startswith("min"):
        numeral = numeral.lower()
    elif quality.startswith("dim"):
        numeral = numeral.lower() + "o"

    # Handle 7th chords
    if "7" in quality:
        numeral += "7"

    # Handle inversions
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


# ── Cadence Detection ────────────────────────────────────────────────────

CADENCE_PATTERNS = {
    "PAC": [  # Perfect Authentic Cadence
        ("V", "I"),
        ("V7", "I"),
        ("V", "i"),
        ("V7", "i"),
        ("V65", "I"),
        ("V43", "I"),
        ("V42", "I"),
    ],
    "IAC": [  # Imperfect Authentic Cadence
        ("V", "I6"),
        ("V7", "I6"),
        ("V", "i6"),
        ("V7", "i6"),
    ],
    "HC": [  # Half Cadence
        ("I", "V"),
        ("i", "V"),
        ("IV", "V"),
        ("iv", "V"),
        ("ii", "V"),
        ("ii6", "V"),
        ("ii7", "V"),
    ],
    "PC": [  # Plagal Cadence
        ("IV", "I"),
        ("iv", "i"),
        ("IV", "i"),
        ("iv", "I"),
    ],
    "DC": [  # Deceptive Cadence
        ("V", "vi"),
        ("V", "VI"),
        ("V7", "vi"),
        ("V7", "VI"),
        ("V", "iv"),
        ("V7", "iv"),
    ],
}


def _normalize_numeral(numeral: str) -> str:
    """Normalize a Roman numeral for comparison (strip inversion, quality)."""
    n = numeral
    # Remove inversion figures
    n = re.sub(r"65$|43$|42$|6$", "", n)
    # Remove 7th suffix
    n = re.sub(r"7$", "", n)
    # Remove diminished/augmented markers
    n = n.replace("o", "").replace("+", "")
    # Remove alteration prefixes for comparison
    n = n.lstrip("b#")
    return n


def _detect_cadences(
    numerals: list[RomanNumeralEvent],
    global_key: str | None = None,
) -> list[CadenceEvent]:
    """Detect cadences from a sequence of Roman numerals.

    Uses two-chord pattern matching.
    """
    cadences: list[CadenceEvent] = []
    if len(numerals) < 2:
        return cadences

    for i in range(len(numerals) - 1):
        curr = numerals[i]
        nxt = numerals[i + 1]

        curr_norm = _normalize_numeral(curr.numeral)
        nxt_norm = _normalize_numeral(nxt.numeral)

        for cadence_type, patterns in CADENCE_PATTERNS.items():
            for pattern in patterns:
                if curr_norm == pattern[0] and nxt_norm == pattern[1]:
                    # Confidence heuristics
                    confidence = 0.6
                    # Longer destination chord → more likely a cadence
                    dest_dur = nxt.end_seconds - nxt.start_seconds
                    if dest_dur >= 1.0:
                        confidence += 0.15
                    # Both chords in same key context → stronger
                    if curr.key_context == nxt.key_context:
                        confidence += 0.1

                    cadences.append(
                        CadenceEvent(
                            type=cadence_type,
                            chords=[curr.numeral, nxt.numeral],
                            start_seconds=curr.start_seconds,
                            end_seconds=nxt.end_seconds,
                            key_context=nxt.key_context or global_key or "C major",
                            confidence=min(confidence, 0.9),
                            provenance=None,
                        )
                    )
                    break  # Only first match per pair

    return cadences


# ── Key Region Detection ──────────────────────────────────────────────────


def _detect_key_regions(
    numerals: list[RomanNumeralEvent],
    global_key: str | None = None,
    window_size: int = 4,
) -> list[KeyRegionEvent]:
    """Detect key regions from Roman numeral sequences.

    Uses a simple heuristic: if a chord acts as tonic (I or i) in a different
    key than the global key for several consecutive chords, it's a likely
    modulation.
    """
    if not numerals or len(numerals) < window_size:
        return []

    regions: list[KeyRegionEvent] = []

    # For now, just return the global key as a single region
    # A proper implementation would need music21's KeyAnalyzer
    if numerals:
        regions.append(
            KeyRegionEvent(
                key=global_key or "C major",
                start_seconds=numerals[0].start_seconds,
                end_seconds=numerals[-1].end_seconds,
                confidence=1.0,
                provenance=None,
            )
        )

    return regions


class TheoryEngine:
    """Production theory interpretation engine.

    Takes chord timeline + key context and produces Roman numerals
    and harmonic function.
    """

    ENGINE = "theory_interpreter"

    def __init__(self) -> None:
        pass

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
        **kwargs: Any,
    ) -> TheoryResult:
        """Interpret theory from a chord timeline.

        Args:
            chords: List of chord events with root/quality or numeral.
            global_key: Optional global key override.

        Returns:
            TheoryResult with Roman numerals and harmonic functions.
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

        # Detect key if not provided
        if not global_key:
            if chords[0].get("root") and chords[0].get("quality"):
                global_key = _detect_key_from_chords(chords)
            else:
                global_key = chords[0].get("global_key", "C major")

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

            # Create Roman numeral event
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
                key_context=global_key or "C major",
                chord_source_id=chord.get("id"),
                provenance=self.provenance.to_dict(),
            )
            roman_numerals.append(rn_event)

            # Create harmonic function event
            function = _classify_function(numeral, global_key)
            func_event = HarmonicFunctionEvent(
                function=function,
                start_seconds=start,
                end_seconds=end,
                roman_numeral=numeral,
                key_context=global_key or "C major",
                roman_numeral_source_id=str(len(roman_numerals) - 1),
                provenance=self.provenance.to_dict(),
            )
            harmonic_functions.append(func_event)

        # Detect cadences from Roman numerals
        cadences = _detect_cadences(roman_numerals, global_key)

        # Detect key regions from Roman numerals
        key_regions = _detect_key_regions(roman_numerals, global_key)

        return TheoryResult(
            roman_numerals=roman_numerals,
            harmonic_functions=harmonic_functions,
            cadences=cadences,
            key_regions=key_regions,
            global_key=global_key,
            provenance=self.provenance,
        )
