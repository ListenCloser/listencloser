from transcription_eval import NoteEvent, compare_events


def test_note_metrics_report_missing_extra_and_timing():
    reference = [NoteEvent(60, 0.0, 0.5), NoteEvent(64, 0.5, 1.0)]
    predicted = [NoteEvent(60, 0.02, 0.48), NoteEvent(67, 0.5, 1.0)]

    metrics = compare_events(reference, predicted)

    assert metrics.matched_notes == 1
    assert metrics.extra_notes == 1
    assert metrics.missing_notes == 1
    assert metrics.precision == 0.5
    assert metrics.recall == 0.5
    assert metrics.f1 == 0.5
    assert metrics.mean_onset_error_ms == 20.0


def test_note_metrics_respect_configured_onset_tolerance():
    reference = [NoteEvent(60, 0.0, 0.5)]
    predicted = [NoteEvent(60, 0.08, 0.58)]

    assert compare_events(reference, predicted, onset_tolerance_s=0.05).matched_notes == 0
    assert compare_events(reference, predicted, onset_tolerance_s=0.1).matched_notes == 1


def test_note_metrics_use_maximum_one_to_one_matching():
    reference = [
        NoteEvent(60, 0.00, 0.50),
        NoteEvent(60, 0.06, 0.56),
    ]
    predicted = [
        NoteEvent(60, 0.04, 0.54),
        NoteEvent(60, 0.09, 0.59),
    ]

    metrics = compare_events(reference, predicted, onset_tolerance_s=0.05)

    assert metrics.matched_notes == 2
    assert metrics.extra_notes == 0
    assert metrics.missing_notes == 0
    assert metrics.precision == 1.0
    assert metrics.recall == 1.0
    assert metrics.f1 == 1.0
