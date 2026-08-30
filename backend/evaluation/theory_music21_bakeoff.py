"""Equal-input Roman-numeral/function bakeoff for issue #657.

This evaluator deliberately gives both implementations only the evidence the
production theory seam receives: a trusted key plus an lv-chordia-style chord
root and quality. It does not provide observed pitches, local-key regions, or a
reference Roman numeral to the OSS candidate.

The OSS candidate uses mir_eval's canonical Harte/JAMS chord parser to realize
only the notes and bass encoded by that root+quality label, then delegates Roman
numeral and harmonic-function interpretation to music21. No repository-owned
chord-quality vocabulary is introduced.

The module is evaluation-only. Production must not import it.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from importlib.metadata import version
from typing import Literal

from mir_eval import chord as mir_chord
from music21 import analysis, key, roman
from music21 import chord as m21_chord

from engines.theory.theory_engine import _chord_name_to_numeral, _classify_function


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


def _jams_label(root: str, quality: str) -> str:
    if root == "N" or quality == "N":
        return "N"
    return f"{root}:{quality}"


def _m21_chord_from_jams(root: str, quality: str) -> m21_chord.Chord:
    """Realize exactly the chord information present in an lv-chordia label."""
    root_number, bitmap, bass_number = mir_chord.encode(
        _jams_label(root, quality),
        reduce_extended_chords=True,
    )
    if root_number < 0:
        raise ValueError("no-chord labels do not carry Roman-numeral evidence")

    root_midi = 60 + int(root_number)
    pitches = [root_midi + interval for interval, active in enumerate(bitmap) if active > 0]

    # Slash-bass information is part of lv-chordia's quality string (e.g.
    # C:maj/3), so preserve it without inventing any observed voicing.
    bass_interval = int(bass_number)
    if bass_interval > 0:
        bass_midi = root_midi + bass_interval - 12
        pitches.insert(0, bass_midi)

    return m21_chord.Chord(pitches)


def baseline_prediction(case: TheoryCase) -> TheoryPrediction:
    """Run the current handwritten production interpretation."""
    numeral = _chord_name_to_numeral(f"{case.root} {case.quality}", case.key_context.split()[0])
    return TheoryPrediction(numeral=numeral, function=_classify_function(numeral, case.key_context))


def music21_prediction(case: TheoryCase) -> TheoryPrediction:
    """Interpret the same JAMS root/quality evidence with mir_eval + music21."""
    if case.root == "N" or case.quality == "N":
        return TheoryPrediction(numeral="", function="AMBIGUOUS")

    chord = _m21_chord_from_jams(case.root, case.quality)
    rn = roman.romanNumeralFromChord(chord, _m21_key(case.key_context))

    fn = analysis.harmonicFunction.romanToFunction(rn, onlyHauptHarmonicFunction=True)
    if fn is None:
        function = "AMBIGUOUS"
    else:
        family = str(fn)[0].upper()
        function = {"T": "TONIC", "S": "SUBDOMINANT", "D": "DOMINANT"}.get(family, "AMBIGUOUS")

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
        "protocol": "trusted_key_plus_lv_chordia_jams_equal_input",
        "candidate": {
            "engine": "mir_eval+music21",
            "mir_eval_version": version("mir_eval"),
            "music21_version": version("music21"),
        },
        "baseline": {"engine": "theory_interpreter", "version": "1.0.0"},
        "metrics": {
            "baseline_numeral_accuracy": _accuracy("baseline_numeral_match"),
            "candidate_numeral_accuracy": _accuracy("candidate_numeral_match"),
            "baseline_function_accuracy": _accuracy("baseline_function_match"),
            "candidate_function_accuracy": _accuracy("candidate_function_match"),
        },
        "examples": [asdict(row) for row in rows],
    }
