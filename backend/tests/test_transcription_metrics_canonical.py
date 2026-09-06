from evaluation.transcription_metrics import Note, compute_note_metrics


def test_maximum_matching_avoids_greedy_under_count():
    reference = [
        Note(60, 0.00, 0.50),
        Note(60, 0.06, 0.56),
    ]
    predicted = [
        Note(60, 0.04, 0.54),
        Note(60, 0.09, 0.59),
    ]

    metrics = compute_note_metrics(predicted, reference, onset_tolerance=0.05)

    assert metrics.onset_matched_count == 2
    assert metrics.onset_f1 == 1.0
    assert metrics.matched_count == 2
    assert metrics.note_f1 == 1.0


def test_offset_scoring_uses_mir_eval_duration_relative_window():
    reference = [Note(60, 0.0, 2.0)]
    predicted = [Note(60, 0.0, 2.3)]

    metrics = compute_note_metrics(
        predicted,
        reference,
        onset_tolerance=0.05,
        offset_tolerance=0.05,
    )

    # mir_eval's canonical rule allows max(20% of the 2 s reference note,
    # 50 ms), so the 300 ms offset error remains a valid note match.
    assert metrics.note_f1 == 1.0
    assert metrics.matched_count == 1


def test_adjacent_semitone_does_not_match_default_pitch_tolerance():
    reference = [Note(60, 0.0, 0.5)]
    predicted = [Note(61, 0.0, 0.5)]

    metrics = compute_note_metrics(predicted, reference)

    assert metrics.onset_f1 == 0.0
    assert metrics.note_f1 == 0.0
