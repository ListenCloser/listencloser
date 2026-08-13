"""Notation-quality diagnostics over generated MusicXML.

These are deliberately cheap, dependency-free string/structural measurements so
they can run in tests and reports without importing music21. Definitions:

- ``note_count``: number of ``<pitch>`` elements (written notes).
- ``tie_element_count``: number of ``<tie `` elements (a start and a stop
  together form one tie, so the true tie count is roughly half of this).
- ``tied_note_ratio``: fraction of written notes that carry a tie start or stop.
- ``rest_count``: number of ``<rest`` elements.
- ``tiny_rest_count``: rests shorter than one 32nd note (a whole measure in 4/4
  is 32 thirty-seconds; ``duration < measure_divisions / 32``).
- ``distinct_duration_count``: number of distinct ``<duration>`` values.
- ``tuplet_count``: number of ``<time-modification>`` elements.
- ``measure_count``: number of ``<measure `` elements.
- ``voice_count``: number of distinct ``<voice>`` values.
"""

from __future__ import annotations

import re
from typing import Any


def musicxml_metrics(musicxml: str) -> dict[str, Any]:
    divisions_match = re.search(r"<divisions>(\d+)</divisions>", musicxml)
    divisions = int(divisions_match.group(1)) if divisions_match else 1

    notes = re.findall(r"<pitch>", musicxml)
    ties = re.findall(r"<tie\s", musicxml)
    rests = re.findall(r"<rest", musicxml)
    durations = [int(d) for d in re.findall(r"<duration>(\d+)</duration>", musicxml)]
    time_mods = re.findall(r"<time-modification>", musicxml)
    measures = re.findall(r"<measure\s", musicxml)
    voices = set(re.findall(r"<voice>(\d+)</voice>", musicxml))

    # A tied note is one that carries a tie start or stop. Approximate by
    # counting notes that immediately precede a tie element within the same
    # <note> block; simpler: treat every tie start/stop as marking one note.
    tied_note_ratio = (len(ties) / len(notes)) if notes else 0.0

    # A whole measure is 4 quarter notes = 4 * divisions. A 32nd note is
    # divisions / 8. Rests shorter than that are "tiny".
    tiny_rest_threshold = divisions / 8
    tiny_rests = 0
    for note_block in re.findall(r"<note>.*?</note>", musicxml, flags=re.DOTALL):
        if "<rest" not in note_block:
            continue
        dur_match = re.search(r"<duration>(\d+)</duration>", note_block)
        if dur_match and int(dur_match.group(1)) < tiny_rest_threshold:
            tiny_rests += 1

    return {
        "note_count": len(notes),
        "tie_element_count": len(ties),
        "tied_note_ratio": round(tied_note_ratio, 4),
        "rest_count": len(rests),
        "tiny_rest_count": tiny_rests,
        "distinct_duration_count": len(set(durations)),
        "tuplet_count": len(time_mods),
        "measure_count": len(measures),
        "voice_count": len(voices),
    }
