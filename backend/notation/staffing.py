"""Piano-aware grand-staff reconstruction.

Turns a single-staff piano transcription into a readable piano grand staff:
one piano part with a treble and a bass staff, grouped with a brace. Note
content (pitch and timing) is never changed — only staff assignment, clefs,
voices, and the MusicXML part/staff structure.

The staff assignment is a small deterministic dynamic program over chord
events. It weighs ledger-line cost (distance from each staff's natural
register) against a continuity penalty for switching staves, so crossing
lines stay on their hand where musically sensible while genuinely wide
textures split across both staves. A hard ``pitch < middle C`` rule is used
only as the implicit tie-break inside the cost model, never as the assignment
itself.
"""

from __future__ import annotations

MIDDLE_C = 60

# Register comfort: treble is natural down to G3, bass up to F4. Notes inside
# [G3, F4] are free on either staff, so the dynamic program resolves them by
# continuity rather than a hard middle-C rule.
_TREBLE_FLOOR = 55
_BASS_CEILING = 65

# Continuity: cost of moving a line from one staff to the other.
_SWITCH_PENALTY = 4.0

# Cost per semitone outside a staff's comfortable register. Kept larger than a
# single switch so genuinely out-of-register material migrates, while notes in
# the shared [G3, F4] band stay with their line via continuity.
_LEDGER_WEIGHT = 2.0

# A chord wider than this (in semitones) may legitimately span both staves.
_WIDE_SPAN = 14


def _staff_penalty(pitch: int, staff: str) -> float:
    if staff == "treble":
        return _LEDGER_WEIGHT * float(max(0, _TREBLE_FLOOR - pitch))
    return _LEDGER_WEIGHT * float(max(0, pitch - _BASS_CEILING))


def _event_cost(pitches: list[int], staff: str) -> float:
    return sum(_staff_penalty(p, staff) for p in pitches)


def split_pitches(pitches: list[int]) -> tuple[list[int], list[int]]:
    """Split a wide chord into (lower, upper) at its largest pitch gap."""
    ordered = sorted(pitches)
    gap_index = 0
    best_gap = -1.0
    for i in range(len(ordered) - 1):
        gap = ordered[i + 1] - ordered[i]
        if gap > best_gap:
            best_gap = gap
            gap_index = i
    return ordered[: gap_index + 1], ordered[gap_index + 1 :]


def assign_staffs(events: list[list[int]]) -> list[str]:
    """Assign each chord event to ``"treble"``, ``"bass"``, or ``"split"``.

    ``events`` is a chronological list; each event is the list of MIDI pitches
    that sound together. Returns a parallel list of ``"treble"``, ``"bass"``,
    or ``"split"`` (for chords wide enough to span both staves).
    """
    n = len(events)
    result: list[str] = [""] * n

    non_wide: list[int] = []
    for i, pitches in enumerate(events):
        if max(pitches) - min(pitches) > _WIDE_SPAN:
            result[i] = "split"
        else:
            non_wide.append(i)

    if not non_wide:
        return result

    m = len(non_wide)
    treble_cost = [_event_cost(events[idx], "treble") for idx in non_wide]
    bass_cost = [_event_cost(events[idx], "bass") for idx in non_wide]

    dp_t = [0.0] * m
    dp_b = [0.0] * m
    dp_t[0] = treble_cost[0]
    dp_b[0] = bass_cost[0]
    came_t = [0] * m
    came_b = [0] * m

    for k in range(1, m):
        stay = dp_t[k - 1]
        switch = dp_b[k - 1] + _SWITCH_PENALTY
        if stay <= switch:
            dp_t[k] = treble_cost[k] + stay
            came_t[k] = 0
        else:
            dp_t[k] = treble_cost[k] + switch
            came_t[k] = 1

        stay = dp_b[k - 1]
        switch = dp_t[k - 1] + _SWITCH_PENALTY
        if stay <= switch:
            dp_b[k] = bass_cost[k] + stay
            came_b[k] = 1
        else:
            dp_b[k] = bass_cost[k] + switch
            came_b[k] = 0

    state = 0 if dp_t[-1] <= dp_b[-1] else 1
    labels = [0] * m
    for k in range(m - 1, -1, -1):
        labels[k] = state
        state = came_t[k] if state == 0 else came_b[k]

    for k, idx in enumerate(non_wide):
        result[idx] = "treble" if labels[k] == 0 else "bass"

    return result


# ---------------------------------------------------------------------------
# music21 reconstruction
# ---------------------------------------------------------------------------


def _source_grid_time_mapper(beat_times: list[float], beat_quarter_length: float):
    """Map source-audio seconds onto score quarter lengths.

    The source beat grid, not the transcription MIDI's placeholder tempo, owns
    score rhythm when it is available. Piecewise interpolation also preserves
    tempo variation between detected beats instead of collapsing the whole
    recording onto the first embedded MIDI tempo.
    """
    import bisect
    import math

    beats = sorted({float(value) for value in beat_times if math.isfinite(value)})
    if len(beats) < 2:
        return None

    intervals = [b - a for a, b in zip(beats, beats[1:], strict=False) if b > a]
    if not intervals:
        return None
    ordered_intervals = sorted(intervals)
    midpoint = len(ordered_intervals) // 2
    if len(ordered_intervals) % 2:
        typical = ordered_intervals[midpoint]
    else:
        typical = (ordered_intervals[midpoint - 1] + ordered_intervals[midpoint]) / 2.0
    if typical <= 0:
        return None

    # Keep audio time zero at score time zero. If the first detected beat begins
    # after the recording starts, the lead-in remains a proportional pickup/rest
    # instead of being shifted negative.
    first_beat_position = beats[0] / typical

    def to_quarter_length(value: float) -> float:
        value = max(0.0, float(value))
        if value <= beats[0]:
            return value / typical * beat_quarter_length

        index = bisect.bisect_right(beats, value) - 1
        if index >= len(beats) - 1:
            beat_position = first_beat_position + len(beats) - 1 + (value - beats[-1]) / typical
        else:
            span = beats[index + 1] - beats[index]
            fraction = (value - beats[index]) / span if span > 0 else 0.0
            beat_position = first_beat_position + index + fraction
        return beat_position * beat_quarter_length

    return to_quarter_length


def grand_staff_from_midi(
    midi_bytes: bytes,
    *,
    beat_times: list[float] | None = None,
    meter_signature: tuple[int, int] | None = None,
):
    """Build a piano grand-staff :class:`~music21.stream.Score` from a MIDI file.

    Reads the quantized note events directly from the MIDI, assigns each to the
    treble or bass staff, and returns a single piano part made of two
    ``PartStaff`` streams with a brace group. Notes crossing a barline are
    re-tied via ``makeTies``. Pitch identity is preserved.

    When a trustworthy source-audio beat grid and inferred meter are supplied,
    seconds are mapped to score quarter lengths from that grid. This prevents a
    transcription MIDI's placeholder tempo/meter metadata from reinterpreting
    otherwise-correct source-aligned note timing during engraving. Without that
    evidence the historical embedded-MIDI behavior is retained.
    """
    import io
    import math
    from collections import defaultdict

    import pretty_midi
    from music21 import chord as chord_mod
    from music21 import clef, instrument, layout, meter, note, stream
    from music21.stream import makeNotation

    pm = pretty_midi.PrettyMIDI(io.BytesIO(midi_bytes))
    tempo = pm.get_tempo_changes()
    bpm = float(tempo[1][0]) if len(tempo[1]) else 120.0
    beat = 60.0 / bpm
    ts = pm.time_signature_changes

    if meter_signature is not None:
        numerator, denominator = int(meter_signature[0]), int(meter_signature[1])
    else:
        numerator = int(ts[0].numerator) if ts else 4
        denominator = int(ts[0].denominator) if ts else 4
    measure_ql = 4.0 * numerator / denominator

    time_mapper = None
    if beat_times is not None and meter_signature is not None:
        time_mapper = _source_grid_time_mapper(beat_times, 4.0 / denominator)

    notes = [n for inst in pm.instruments if not inst.is_drum for n in inst.notes]
    events: list[tuple[float, float, int]] = []
    for n in notes:
        if time_mapper is None:
            onset = n.start / beat
            duration = (n.end - n.start) / beat
        else:
            onset = time_mapper(n.start)
            duration = time_mapper(n.end) - onset
        events.append((onset, max(duration, 1e-6), n.pitch))
    events.sort(key=lambda e: e[0])

    # Group simultaneous pitches into onset events for staff assignment (a chord
    # stays together), but keep each note's own duration for placement.
    onset_pitches: dict[float, list[int]] = defaultdict(list)
    for onset, _dur, pitch in events:
        onset_pitches[round(onset, 4)].append(pitch)
    ordered_onsets = sorted(onset_pitches)
    labels = assign_staffs([onset_pitches[o] for o in ordered_onsets])

    # Map each onset to the pitches assigned to treble / bass.
    onset_treble: dict[float, set[int]] = defaultdict(set)
    onset_bass: dict[float, set[int]] = defaultdict(set)
    for onset, label in zip(ordered_onsets, labels, strict=False):
        pitches = onset_pitches[onset]
        if label == "split":
            lower, upper = split_pitches(pitches)
            onset_bass[onset] = set(lower)
            onset_treble[onset] = set(upper)
        elif label == "treble":
            onset_treble[onset] = set(pitches)
        else:
            onset_bass[onset] = set(pitches)

    max_end = max((onset + dur for onset, dur, _ in events), default=0.0)
    n_measures = max(1, int(math.ceil(max_end / measure_ql)))

    treble = stream.PartStaff(id="P1-Staff1")
    bass = stream.PartStaff(id="P1-Staff2")
    treble.insert(0, instrument.Piano())
    bass.insert(0, instrument.Piano())

    treble_measures = [stream.Measure(number=i + 1) for i in range(n_measures)]
    bass_measures = [stream.Measure(number=i + 1) for i in range(n_measures)]
    treble_measures[0].insert(0, clef.TrebleClef())
    treble_measures[0].insert(0, meter.TimeSignature(f"{numerator}/{denominator}"))
    bass_measures[0].insert(0, clef.BassClef())
    bass_measures[0].insert(0, meter.TimeSignature(f"{numerator}/{denominator}"))

    # Group notes by (onset, duration, staff) so simultaneous notes with the
    # same duration become a chord while different durations stay separate.
    by_key: dict[tuple[float, float, str], list[int]] = defaultdict(list)
    for onset, dur, pitch in events:
        onset = round(onset, 4)
        if pitch in onset_bass.get(onset, ()):
            staff = "bass"
        elif pitch in onset_treble.get(onset, ()):
            staff = "treble"
        else:
            # A pitch shared by both split halves (rare): default to treble.
            staff = "treble"
        by_key[(onset, round(dur, 4), staff)].append(pitch)

    for (onset, dur, staff), pitches in sorted(by_key.items()):
        measures = treble_measures if staff == "treble" else bass_measures
        mi = int(onset // measure_ql)
        local = onset - mi * measure_ql
        if len(pitches) == 1:
            obj = note.Note(pitches[0], quarterLength=dur)
        else:
            obj = chord_mod.Chord([note.Note(p) for p in sorted(pitches)], quarterLength=dur)
        measures[mi].insert(local, obj)

    for m in treble_measures:
        treble.append(m)
    for m in bass_measures:
        bass.append(m)

    new_score = stream.Score()
    new_score.insert(0, treble)
    new_score.insert(0, bass)
    new_score.insert(0, layout.StaffGroup(treble, bass, symbol="brace"))

    makeNotation.makeTies(new_score, inPlace=True)
    return new_score
