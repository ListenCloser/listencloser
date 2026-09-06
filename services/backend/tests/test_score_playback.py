import io

import pretty_midi

from music_features import measure_start_seconds


def _four_measure_midi() -> bytes:
    pm = pretty_midi.PrettyMIDI(initial_tempo=120)
    instrument = pretty_midi.Instrument(program=0)
    for i in range(4):
        instrument.notes.append(
            pretty_midi.Note(velocity=80, pitch=60 + i, start=i * 2.0, end=i * 2.0 + 0.5)
        )
    pm.instruments.append(instrument)
    buffer = io.BytesIO()
    pm.write(buffer)
    return buffer.getvalue()


def test_measure_start_seconds_follows_a_4_4_grid():
    starts = measure_start_seconds(_four_measure_midi())
    assert starts[0] == 0.0
    assert abs(starts[1] - 2.0) < 0.01
    assert abs(starts[2] - 4.0) < 0.01
    assert len(starts) >= 4


def test_measure_start_seconds_returns_empty_for_garbage():
    assert measure_start_seconds(b"not midi") == []
