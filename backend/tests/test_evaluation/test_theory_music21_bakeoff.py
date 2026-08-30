"""Decision-producing tests for the #657 equal-input theory bakeoff."""

from evaluation.theory_music21_bakeoff import (
    TheoryCase,
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


def test_music21_matches_or_beats_handwritten_core_contract():
    report = evaluate_cases(_CORE_CASES)
    metrics = report["metrics"]

    assert metrics["candidate_numeral_accuracy"] >= metrics["baseline_numeral_accuracy"]
    assert metrics["candidate_function_accuracy"] >= metrics["baseline_function_accuracy"]
    assert metrics["candidate_numeral_accuracy"] == 1.0
    assert metrics["candidate_function_accuracy"] == 1.0


def test_music21_handles_quality_evidence_handwritten_mapper_collapses():
    # The current mapper treats hdim7 as a generic uppercase seventh because
    # it recognizes neither the diminished triad nor the half-diminished kind.
    # music21 can express the supplied root+quality evidence without any
    # observed voicing or inversion input.
    prediction = music21_prediction(
        TheoryCase("leading-tone-half-dim", "C major", "B", "hdim7")
    )
    assert prediction.numeral in {"viiø7", "vii/o7"}


def test_music21_accepts_the_lv_chordia_quality_adapter_vocabulary():
    qualities = [
        "maj",
        "min",
        "dim",
        "aug",
        "7",
        "maj7",
        "min7",
        "dim7",
        "hdim7",
        "minmaj7",
        "maj6",
        "min6",
        "9",
        "maj9",
        "min9",
        "sus2",
        "sus4",
    ]
    for quality in qualities:
        prediction = music21_prediction(TheoryCase(f"quality-{quality}", "C major", "C", quality))
        assert prediction.numeral
