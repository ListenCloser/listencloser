"""Notation-quality diagnostics using music21 for reliable structural inspection."""

from __future__ import annotations

import math
from contextlib import suppress
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class NotationDiagnostics:
    parse_valid: bool
    total_note_count: int
    measure_count: int
    short_note_count: int
    tie_count: int
    tuplet_count: int
    voice_count: int
    measure_duration_min: float | None
    measure_duration_max: float | None
    measure_duration_std: float | None
    issues: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "parse_valid": self.parse_valid,
            "total_note_count": self.total_note_count,
            "measure_count": self.measure_count,
            "short_note_count": self.short_note_count,
            "tie_count": self.tie_count,
            "tuplet_count": self.tuplet_count,
            "voice_count": self.voice_count,
            "measure_duration_min": (
                round(self.measure_duration_min, 3)
                if self.measure_duration_min is not None
                else None
            ),
            "measure_duration_max": (
                round(self.measure_duration_max, 3)
                if self.measure_duration_max is not None
                else None
            ),
            "measure_duration_std": (
                round(self.measure_duration_std, 3)
                if self.measure_duration_std is not None
                else None
            ),
            "issues": self.issues,
        }


_SHORT_NOTE_DIVISION = 0.25


def diagnose_musicxml(musicxml_bytes: bytes) -> NotationDiagnostics:
    """Inspect a MusicXML string using music21 for structural diagnostics.

    Falls back to regex diagnostics when music21 is not available.
    """
    import io
    import re

    def _regex_diagnostics():
        text = musicxml_bytes.decode("utf-8", errors="replace")
        parse_valid = "<score-partwise" in text.lower()
        issues: list[str] = []
        if not parse_valid:
            issues.append("not valid MusicXML (missing <score-partwise>)")
        notes = re.findall(r"<note[ >]", text)
        measures = re.findall(r"<measure\b", text)
        short_note_count = sum(
            1 for t in re.findall(r"<duration>(\d+)</duration>", text) if int(t) <= 2
        )
        tie_count = len(re.findall(r"<tie\b", text))
        tuplet_count = len(re.findall(r"<tuplet", text))
        voice_count = len(set(re.findall(r"<voice>(\d+)</voice>", text)))
        measure_durations: list[int] = []
        for m in re.finditer(r"<measure\b.*?</measure>", text, re.DOTALL):
            m_durs = [int(d) for d in re.findall(r"<duration>(\d+)</duration>", m.group())]
            if m_durs:
                measure_durations.append(sum(m_durs))
        dur_min = min(measure_durations) if measure_durations else None
        dur_max = max(measure_durations) if measure_durations else None
        if len(measure_durations) >= 2 and dur_min and dur_max and dur_max > dur_min * 2:
            issues.append(f"measure duration inconsistency: {dur_min}–{dur_max}")
        dur_std = None
        if len(measure_durations) >= 2:
            avg = sum(measure_durations) / len(measure_durations)
            dur_std = math.sqrt(
                sum((d - avg) ** 2 for d in measure_durations) / len(measure_durations)
            )
        return NotationDiagnostics(
            parse_valid=parse_valid,
            total_note_count=len(notes),
            measure_count=len(measures),
            short_note_count=short_note_count,
            tie_count=tie_count,
            tuplet_count=tuplet_count,
            voice_count=voice_count,
            measure_duration_min=dur_min,
            measure_duration_max=dur_max,
            measure_duration_std=dur_std,
            issues=issues,
        )

    try:
        from music21 import converter

        issues: list[str] = []
        score = converter.parse(io.BytesIO(musicxml_bytes), format="musicxml")
    except Exception:
        return _regex_diagnostics()

    parts = list(score.parts) if score.parts is not None else []
    all_notes: list[Any] = []
    tie_count = 0
    tuplet_count = 0
    voice_ids: set[int] = set()
    for part in parts:
        for measure in part.getElementsByClass("Measure"):
            all_notes.extend(measure.notesAndRests)
            tie_count += len(measure.getElementsByClass("Tie"))
            tuplet_count += len(measure.getElementsByClass("Tuplet"))
            for el in measure.recurse():
                if hasattr(el, "id") and el.id is not None:
                    with suppress(ValueError, TypeError):
                        voice_ids.add(int(el.id))

    note_objects = [n for n in all_notes if hasattr(n, "pitch") and n.pitch is not None]
    total_note_count = len(note_objects)
    measure_count = len(list(score.parts[0].getElementsByClass("Measure"))) if parts else 0

    short_note_count = sum(
        1
        for n in note_objects
        if n.duration is not None and float(n.duration.quarterLength) <= _SHORT_NOTE_DIVISION
    )

    measure_durations: list[float] = []
    for part in parts:
        for m in part.getElementsByClass("Measure"):
            d = float(m.duration.quarterLength) if m.duration is not None else 0.0
            if d > 0:
                measure_durations.append(d)

    dur_min = float(min(measure_durations)) if measure_durations else None
    dur_max = float(max(measure_durations)) if measure_durations else None
    if len(measure_durations) >= 2 and dur_min and dur_max and dur_max > dur_min * 2:
        issues.append(
            f"measure duration inconsistency: {dur_min:.1f}–{dur_max:.1f} quarter-lengths"
        )
    dur_std = None
    if len(measure_durations) >= 2:
        avg = sum(measure_durations) / len(measure_durations)
        variance = sum((d - avg) ** 2 for d in measure_durations) / len(measure_durations)
        dur_std = math.sqrt(variance)

    voice_count = len(voice_ids) or len(parts)

    return NotationDiagnostics(
        parse_valid=True,
        total_note_count=total_note_count,
        measure_count=measure_count,
        short_note_count=short_note_count,
        tie_count=tie_count,
        tuplet_count=tuplet_count,
        voice_count=voice_count,
        measure_duration_min=dur_min,
        measure_duration_max=dur_max,
        measure_duration_std=dur_std,
        issues=issues,
    )
