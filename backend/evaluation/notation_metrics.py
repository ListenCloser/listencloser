"""Notation-quality diagnostics (structural, not subjective)."""

from __future__ import annotations

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


def diagnose_musicxml(musicxml_bytes: bytes) -> NotationDiagnostics:
    """Inspect a MusicXML string for structural diagnostics."""
    import math
    import re

    try:
        text = musicxml_bytes.decode("utf-8", errors="replace")
    except Exception:
        text = musicxml_bytes.decode("latin-1", errors="replace")

    parse_valid = "<score-partwise" in text.lower()
    issues: list[str] = []
    if not parse_valid:
        issues.append("not valid MusicXML (missing <score-partwise>)")

    notes = re.findall(r"<note[ >]", text)
    total_note_count = len(notes)

    measures = re.findall(r"<measure\b", text)
    measure_count = len(measures)

    # Very short notes: 32nd / 64th / 128th / 256th
    short_note_count = sum(
        1 for tag in re.findall(r"<duration>(\d+)</duration>", text) if int(tag) <= 2
    )

    tie_count = len(re.findall(r"<tie\b", text))
    tuplet_count = len(re.findall(r"<tuplet", text))
    voice_count = len(set(re.findall(r"<voice>(\d+)</voice>", text)))

    # Measure duration stats
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
    if len(measure_durations) >= 2 and measure_durations:
        avg = sum(measure_durations) / len(measure_durations)
        variance = sum((d - avg) ** 2 for d in measure_durations) / len(measure_durations)
        dur_std = math.sqrt(variance)

    return NotationDiagnostics(
        parse_valid=parse_valid,
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
