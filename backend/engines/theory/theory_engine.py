"""Theory interpretation engine for harmonic analysis.

Takes a trusted chord timeline + trusted key context and produces Roman-numeral
and harmonic-function evidence through task-standard MIR/musicology libraries.
Cadence and local-key-region capabilities remain intentionally withheld.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from importlib.metadata import version
from typing import Any

from mir_eval import chord as mir_chord
from music21 import analysis, key, roman
from music21 import chord as m21_chord

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


def _m21_pitch_name(name: str) -> str:
    """Translate JAMS flat spelling (Bb) to music21 spelling (B-)."""
    if len(name) >= 2 and name[1] == "b":
        return f"{name[0]}-{name[2:]}"
    return name


def _m21_key(key_context: str) -> key.Key:
    """Preserve the trusted tonic and mode when constructing a music21 key."""
    parts = key_context.split()
    tonic = _m21_pitch_name(parts[0])
    mode = parts[1].lower() if len(parts) > 1 else "major"
    return key.Key(tonic, mode)


def _m21_chord_from_jams(root: str, quality: str) -> m21_chord.Chord:
    """Realize exactly the pitch-class and bass evidence in a Harte/JAMS label."""
    root_number, bitmap, bass_number = mir_chord.encode(
        f"{root}:{quality}",
        reduce_extended_chords=True,
    )
    root_midi = 60 + int(root_number)
    pitches = [root_midi + interval for interval, active in enumerate(bitmap) if active > 0]

    # Slash-bass information is explicitly present in labels such as C:maj/3.
    # Preserve that evidence without inventing an observed performance voicing.
    bass_interval = int(bass_number)
    if bass_interval > 0:
        pitches.insert(0, root_midi + bass_interval - 12)

    return m21_chord.Chord(pitches)


def _roman_from_event(chord: dict[str, Any], key_context: str) -> roman.RomanNumeral | None:
    """Interpret one trusted chord event without adding information it does not carry."""
    key_obj = _m21_key(key_context)

    supplied_numeral = chord.get("numeral")
    if supplied_numeral and not chord.get("root"):
        return roman.RomanNumeral(str(supplied_numeral), key_obj)

    root = chord.get("root")
    quality = chord.get("quality")
    if not root or not quality or root == "N" or quality == "N":
        return None

    try:
        m21_chord = _m21_chord_from_jams(str(root), str(quality))
    except mir_chord.InvalidChordException:
        logger.warning(
            "theory_withheld_invalid_chord_label",
            extra={"root": root, "quality": quality},
        )
        return None

    return roman.romanNumeralFromChord(m21_chord, key_obj)


def _harmonic_function(rn: roman.RomanNumeral) -> str:
    """Adapt music21 Hauptfunktion output to the product's four-value enum."""
    function = analysis.harmonicFunction.romanToFunction(
        rn,
        onlyHauptHarmonicFunction=True,
    )
    if function is None:
        return "AMBIGUOUS"
    family = str(function)[0].upper()
    return {"T": "TONIC", "S": "SUBDOMINANT", "D": "DOMINANT"}.get(family, "AMBIGUOUS")


def _inversion_name(rn: roman.RomanNumeral) -> str | None:
    """Adapt music21's inversion index to the existing event contract."""
    return {1: "first", 2: "second", 3: "third"}.get(rn.inversion())


class TheoryEngine:
    """Production theory interpretation backed by mir_eval + music21."""

    ENGINE = "theory_interpreter"

    @property
    def provenance(self) -> EngineProvenance:
        return EngineProvenance(
            engine=self.ENGINE,
            library_version=version("music21"),
            model="mir_eval_harte_to_music21",
            parameters={
                "mir_eval_version": version("mir_eval"),
                "input_contract": "trusted_key_plus_lv_chordia_jams",
            },
        )

    def analyze(
        self,
        chords: list[dict[str, Any]],
        global_key: str | None = None,
        key_source: str | None = None,
        key_provenance: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> TheoryResult:
        """Interpret production-safe theory from a trusted chord timeline.

        Roman numerals and harmonic functions are withheld when no trusted key
        exists. Invalid/no-chord labels are skipped instead of being coerced to
        a fabricated tonic. Cadence and local-key-region outputs remain empty.
        """
        if not chords:
            return TheoryResult(
                roman_numerals=[],
                harmonic_functions=[],
                cadences=[],
                key_regions=[],
                global_key=global_key,
                provenance=self.provenance,
            )

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

        roman_numerals: list[RomanNumeralEvent] = []
        harmonic_functions: list[HarmonicFunctionEvent] = []
        provenance = self.provenance.to_dict()

        for chord in chords:
            rn = _roman_from_event(chord, global_key)
            if rn is None:
                continue

            start = float(chord.get("start", 0))
            end = float(chord.get("end", 0))
            secondary = rn.secondaryRomanNumeral
            numeral = rn.figure

            roman_numerals.append(
                RomanNumeralEvent(
                    numeral=numeral,
                    degree=int(rn.scaleDegree),
                    quality=rn.quality,
                    seventh=bool(rn.isSeventh()),
                    inversion=_inversion_name(rn),
                    is_secondary=secondary is not None,
                    secondary_target=secondary.figure if secondary is not None else None,
                    start_seconds=start,
                    end_seconds=end,
                    key_context=global_key,
                    key_source=key_source,
                    key_provenance=key_provenance,
                    chord_source_id=chord.get("id"),
                    provenance=provenance,
                )
            )
            harmonic_functions.append(
                HarmonicFunctionEvent(
                    function=_harmonic_function(rn),
                    start_seconds=start,
                    end_seconds=end,
                    roman_numeral=numeral,
                    key_context=global_key,
                    key_source=key_source,
                    key_provenance=key_provenance,
                    roman_numeral_source_id=str(len(roman_numerals) - 1),
                    provenance=provenance,
                )
            )

        return TheoryResult(
            roman_numerals=roman_numerals,
            harmonic_functions=harmonic_functions,
            cadences=[],
            key_regions=[],
            global_key=global_key,
            provenance=self.provenance,
        )
