"""Decision-producing tests for the #657 equal-input theory bakeoff."""

from evaluation.theory_music21_bakeoff import (
    TheoryCase,
    baseline_prediction,
    evaluate_cases,
    music21_prediction,
)


_CORE_CASES = [
    TheoryCase("c-major-tonic", "C major", "C", "maj", "I", "TONIC"),
    TheoryCase("c-major-supertonic", "C major", "D", "min", "ii", "SUBDOMINANT"),
    TheoryCase("c-major-subdominant", "C major", "F", "maj", "IV", "SUBDOMINANT"),
    TheoryCase("c-major-dominant", "C major", "G", "maj", "V", "DOMINANT"),
    TheoryCase("c-major-submediant", "C major", "A", "min", "vi", "TONIC"),
    TheoryCase("c-major-dominant7", "C major", "G", "7", "V7", "DOMINANT"),
    TheoryCase("c-major-supertonic7", "C major", "D", "min7", "ii7", "SUBDOMINANT"),
    TheoryCase("a-minor-tonic", "A minor", "A", "min", "i", "TONIC"),
    TheoryCase("a-minor-subdominant", "A minor", "D", "min", "iv", "SUBDOMINANT"),
    TheoryCase("a-minor-dominant", "A minor", "E", "maj", "V", "DOMINANT"),
]

# Exact non-N suffixes shipped by lv-chordia's `submission` dictionary.
# Source: openmirlab/lv-chordia lv_chordia/data/submission_chord_list.txt.
_SUBMISSION_QUALITIES = [
    "min/b7",
    "min/2",
    "maj/b7",
    "maj/2",
    "sus4(b7)",
    "sus2",
    "sus4",
    "13",
    "11",
    "min9",
    "9",
    "maj9",
    "dim7",
    "hdim7",
    "min7",
    "7",
    "maj7",
    "min/5",
    "min/b3",
    "maj/5",
    "maj/3",
    "dim",
    "aug",
    "min",
    "maj",
]


def test_music21_matches_or_beats_handwritten_core_contract():
    report = evaluate_cases(_CORE_CASES)
    metrics = report["metrics"]

    assert metrics["candidate_numeral_accuracy"] >= metrics["baseline_numeral_accuracy"]
    assert metrics["candidate_function_accuracy"] >= metrics["baseline_function_accuracy"]
    assert metrics["candidate_numeral_accuracy"] == 1.0
    assert metrics["candidate_function_accuracy"] == 1.0


def test_music21_handles_quality_evidence_handwritten_mapper_collapses():
    prediction = music21_prediction(
        TheoryCase("leading-tone-half-dim", "C major", "B", "hdim7")
    )
    assert "vii" in prediction.numeral.lower()
    assert "7" in prediction.numeral


def test_music21_accepts_authoritative_lv_chordia_submission_vocabulary():
    for quality in _SUBMISSION_QUALITIES:
        prediction = music21_prediction(TheoryCase(f"quality-{quality}", "C major", "C", quality))
        assert prediction.numeral, quality


def test_music21_preserves_slash_bass_that_handwritten_mapper_drops():
    case = TheoryCase("tonic-first-inversion", "C major", "C", "maj/3")

    assert baseline_prediction(case).numeral == "I"
    assert music21_prediction(case).numeral == "I6"
