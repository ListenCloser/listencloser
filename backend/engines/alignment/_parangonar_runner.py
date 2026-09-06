"""Standalone Parangonar runner for the isolated #1083 runtime.

This file intentionally imports no ListenCloser modules. It is executed by the
separately provisioned Python interpreter so Parangonar does not become an
implicit dependency of the API process before the canonical lock owns it.
"""

from __future__ import annotations

import importlib.metadata
import json
import sys
from pathlib import Path
from typing import Any

PARANGONAR_VERSION = "3.3.3"
PARTITURA_VERSION = "1.9.0"
OUTPUT_PREFIX = "LISTENCLOSER_PARANGONAR_JSON="


def _score_events(note_array: Any) -> list[dict[str, Any]]:
    """Preserve literal Partitura score-note fields needed for cross-view identity."""

    events: list[dict[str, Any]] = []
    for row in note_array:
        events.append(
            {
                "id": str(row["id"]),
                # Keep the historical generic onset for the normalization seam.
                "onset": float(row["onset_beat"]),
                "pitch": int(row["pitch"]),
                "onset_beat": float(row["onset_beat"]),
                "duration_beat": float(row["duration_beat"]),
                "onset_quarter": float(row["onset_quarter"]),
                "duration_quarter": float(row["duration_quarter"]),
                "onset_div": int(row["onset_div"]),
                "duration_div": int(row["duration_div"]),
                "voice": int(row["voice"]),
                "staff": int(row["staff"]),
                "is_grace": bool(row["is_grace"]),
                "rel_onset_div": int(row["rel_onset_div"]),
                "total_measure_divs": int(row["tot_measure_div"]),
            }
        )
    return events


def _performance_events(note_array: Any) -> list[dict[str, Any]]:
    """Preserve literal Partitura performed-note fields from the exact MIDI parse."""

    events: list[dict[str, Any]] = []
    for row in note_array:
        events.append(
            {
                "id": str(row["id"]),
                "onset": float(row["onset_sec"]),
                "pitch": int(row["pitch"]),
                "onset_seconds": float(row["onset_sec"]),
                "duration_seconds": float(row["duration_sec"]),
                "velocity": int(row["velocity"]),
                "track": int(row["track"]),
                "channel": int(row["channel"]),
            }
        )
    return events


def _alignment_records(raw_alignment: list[dict[str, Any]]) -> list[dict[str, str]]:
    records: list[dict[str, str]] = []
    for raw in raw_alignment:
        record = {"label": str(raw["label"])}
        if raw.get("score_id") is not None:
            record["score_id"] = str(raw["score_id"])
        if raw.get("performance_id") is not None:
            record["performance_id"] = str(raw["performance_id"])
        records.append(record)
    return records


def _single_score_part(score: Any) -> Any:
    parts = list(getattr(score, "parts", []))
    if not parts:
        try:
            return score[0]
        except (IndexError, KeyError, TypeError) as exc:
            raise RuntimeError("MusicXML contains no score part") from exc
    if len(parts) == 1:
        return parts[0]

    import partitura as pt

    return pt.score.merge_parts(parts)


def _first_performed_part(performance: Any) -> Any:
    performed_parts = list(getattr(performance, "performedparts", []))
    if performed_parts:
        return performed_parts[0]
    try:
        return performance[0]
    except (IndexError, KeyError, TypeError) as exc:
        raise RuntimeError("performance MIDI contains no performed part") from exc


def run(score_path: Path, performance_path: Path) -> dict[str, Any]:
    actual_parangonar = importlib.metadata.version("parangonar")
    actual_partitura = importlib.metadata.version("partitura")
    if actual_parangonar != PARANGONAR_VERSION:
        raise RuntimeError(f"expected parangonar {PARANGONAR_VERSION}, found {actual_parangonar}")
    if actual_partitura != PARTITURA_VERSION:
        raise RuntimeError(f"expected partitura {PARTITURA_VERSION}, found {actual_partitura}")

    import partitura as pt
    from parangonar import DualDTWNoteMatcher

    score = pt.load_musicxml(str(score_path), force_note_ids=True, validate=True)
    score_part = _single_score_part(score)
    performance = pt.load_performance_midi(str(performance_path))
    performance_part = _first_performed_part(performance)
    score_notes = score_part.note_array(
        include_grace_notes=True,
        include_staff=True,
        include_metrical_position=True,
    )
    performance_notes = performance_part.note_array()

    payload: dict[str, Any] = {
        "parangonar_version": actual_parangonar,
        "partitura_version": actual_partitura,
        "matcher": "DualDTWNoteMatcher",
        "parameters": {
            "process_ornaments": False,
            "force_note_ids": True,
            "musicxml_validation": True,
            "identity_fields": "partitura_native_v1",
        },
        "score_events": _score_events(score_notes),
        "performance_events": _performance_events(performance_notes),
        "alignment": None,
        "failure": None,
    }
    try:
        matcher = DualDTWNoteMatcher()
        raw_alignment = matcher(score_notes, performance_notes, process_ornaments=False)
        payload["alignment"] = _alignment_records(raw_alignment)
    except Exception as exc:  # matcher failures are product evidence, not fallback triggers
        payload["failure"] = f"{type(exc).__name__}: {exc}"
    return payload


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit("usage: _parangonar_runner.py SCORE.musicxml PERFORMANCE.mid")
    payload = run(Path(sys.argv[1]), Path(sys.argv[2]))
    print(f"{OUTPUT_PREFIX}{json.dumps(payload, separators=(',', ':'), sort_keys=True)}")


if __name__ == "__main__":
    main()
