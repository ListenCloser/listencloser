"""Equal-input Roman-numeral/function bakeoff for issue #657.

This evaluator deliberately gives both implementations only the evidence the
production theory seam receives: a trusted key plus an lv-chordia-style chord
root and quality.  It does not provide observed pitches, bass/inversion, local
key regions, or a reference Roman numeral to the OSS candidate.

The module is evaluation-only.  Production must not import it.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from importlib.metadata import version
from typing import Literal

from music21 import analysis, harmony, key, roman

from engines.theory.theory_engine import _chord_name_to_numeral, _classify_function


# JAMS/lv-chordia quality token -> music21 ChordSymbol suffix.  This is format
# normalization only: every realized pitch is determined by the same root +
# quality evidence already supplied to the handwritten production adapter.
_QUALITY_SUFFIX = {
    "maj": "",
    "min": "m",
    "dim": "dim",
    "aug": "+",
    "7": "7",
    "maj7": "M7",
    "min7": "m7",
    "dim7": "dim7",
    "hdim7": "m7b5",
    "minmaj7": "mM7",
    "maj6": "6",
    "min6": "m6",
    "9": "9",
    "maj9": "Maj9",
    "min9": "m9",
    "sus2": "sus2",
    "sus4": "sus4",
}


@dataclass(frozen=True)
class TheoryCase:
    """One production-shaped root/quality + trusted-key example."""

    case_id: str
    key_context: str
    root: str
    quality: str
    expected_numeral: str | None = None
    expected_function: Literal["TONIC", "SUBDOMINANT", "DOMINANT", "AMBIGUOUS"] | None = None
    source: str = "synthetic_contract"


@dataclass(frozen=True)
class TheoryPrediction:
    numeral: str
    function: str


@dataclass(frozen=True)
class CaseResult:
    case: TheoryCase
    baseline: TheoryPrediction
    candidate: TheoryPrediction
    baseline_numeral_match: bool | None
    candidate_numeral_match: bool | None
    baseline_function_match: bool | None
    candidate_function_match: bool | None


def _m21_pitch_name(name: str) -> str:
    """Translate JAMS flat spelling (Bb) to music21 spelling (B-)."""
    if len(name) >= 2 and name[1] == "b":
        return f"{name[0]}-{name[2:]}"
    return name


def _m21_key(key_context: str) -> key.Key:
    parts = key_context.split()
    tonic = _m21_pitch_name(parts[0])
    mode = parts[1].lower() if len(parts) > 1 else "major"
    return key.Key(tonic, mode)


def baseline_prediction(case: TheoryCase) -> TheoryPrediction:
    """Run the current handwritten production interpretation."""
    numeral = _chord_name_to_numeral(f"{case.root} {case.quality}", case.key_context.split()[0])
    return TheoryPrediction(numeral=numeral, function=_classify_function(numeral, case.key_context))


def music21_prediction(case: TheoryCase) -> TheoryPrediction:
    """Interpret the same root/quality evidence with music21.

    ``ChordSymbol`` realizes a canonical root-position pitch set from the chord
    *kind*.  Those pitches are a deterministic encoding of the supplied quality,
    not richer observed voicing.  No bass/inversion evidence is supplied.
    """
    try:
        suffix = _QUALITY_SUFFIX[case.quality]
    except KeyError as exc:
        raise ValueError(f"unsupported lv-chordia quality for bakeoff: {case.quality}") from exc

    symbol = harmony.ChordSymbol(f"{_m21_pitch_name(case.root)}{suffix}")
    rn = roman.romanNumeralFromChord(symbol, _m21_key(case.key_context))

    fn = analysis.harmonicFunction.romanToFunction(rn, onlyHauptHarmonicFunction=True)
    if fn is None:
        function = "AMBIGUOUS"
    else:
        family = str(fn)[0].upper()
        function = {"T": "TONIC", "S": "SUBDOMINANT", "D": "DOMINANT"}.get(
            family, "AMBIGUOUS"
        )

    return TheoryPrediction(numeral=rn.figure, function=function)


def evaluate_cases(cases: list[TheoryCase]) -> dict:
    """Return per-example and aggregate equal-input evidence."""
    rows: list[CaseResult] = []
    for case in cases:
        baseline = baseline_prediction(case)
        candidate = music21_prediction(case)
        rows.append(
            CaseResult(
                case=case,
                baseline=baseline,
                candidate=candidate,
                baseline_numeral_match=(
                    baseline.numeral == case.expected_numeral
                    if case.expected_numeral is not None
                    else None
                ),
                candidate_numeral_match=(
                    candidate.numeral == case.expected_numeral
                    if case.expected_numeral is not None
                    else None
                ),
                baseline_function_match=(
                    baseline.function == case.expected_function
                    if case.expected_function is not None
                    else None
                ),
                candidate_function_match=(
                    candidate.function == case.expected_function
                    if case.expected_function is not None
                    else None
                ),
            )
        )

    def _accuracy(field: str) -> float | None:
        values = [getattr(row, field) for row in rows if getattr(row, field) is not None]
        return sum(values) / len(values) if values else None

    return {
        "schema_version": 1,
        "protocol": "trusted_key_plus_root_quality_equal_input",
        "candidate": {"engine": "music21", "version": version("music21")},
        "baseline": {"engine": "theory_interpreter", "version": "1.0.0"},
        "metrics": {
            "baseline_numeral_accuracy": _accuracy("baseline_numeral_match"),
            "candidate_numeral_accuracy": _accuracy("candidate_numeral_match"),
            "baseline_function_accuracy": _accuracy("baseline_function_match"),
            "candidate_function_accuracy": _accuracy("candidate_function_match"),
        },
        "examples": [asdict(row) for row in rows],
    }
