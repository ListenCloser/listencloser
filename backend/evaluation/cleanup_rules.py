"""Candidate transcription-cleanup rules (evaluation-oriented).

Configs compared in the #215 experiment:

- ``A`` raw: Basic Pitch output, no post-processing.
- ``B`` existing: the current ``_clean_midi`` policy (out-of-range, very short,
  low-velocity-short, same-pitch overlap merge).
- ``C`` model-score: drop notes below an amplitude (mean note-frame activation)
  threshold only.
- ``D`` model-score + context: drop weak notes AND isolated/extreme-register/
  fragmented notes, using model evidence plus local pitch context.

All rules operate on note dicts ``{pitch, start, end, velocity, amplitude}`` and
return ``(kept_notes, report)``.  None of these are enabled in production
without benchmark evidence.
"""

from __future__ import annotations

from typing import Any

_MIN_PITCH = 21
_MAX_PITCH = 108
_MIN_DURATION = 0.075
_LOW_VELOCITY = 18
_LOW_VELOCITY_SHORT_DURATION = 0.16


def _sorted(notes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(notes, key=lambda n: (n["pitch"], n["start"]))


def cleanup_raw(
    notes: list[dict[str, Any]], **_: Any
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    return list(notes), {"profile": "raw", "input_notes": len(notes), "kept_notes": len(notes)}


def cleanup_existing(
    notes: list[dict[str, Any]], **_: Any
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Mirror of ``_clean_midi`` operating on note dicts."""
    report = {
        "profile": "existing",
        "input_notes": len(notes),
        "removed_out_of_range": 0,
        "removed_short": 0,
        "removed_low_velocity": 0,
        "merged_overlaps": 0,
    }
    filtered = []
    for n in notes:
        dur = n["end"] - n["start"]
        if n["pitch"] < _MIN_PITCH or n["pitch"] > _MAX_PITCH:
            report["removed_out_of_range"] += 1
        elif dur < _MIN_DURATION:
            report["removed_short"] += 1
        elif n["velocity"] < _LOW_VELOCITY and dur < _LOW_VELOCITY_SHORT_DURATION:
            report["removed_low_velocity"] += 1
        else:
            filtered.append(dict(n))
    filtered = _sorted(filtered)
    cleaned = []
    for n in filtered:
        if not cleaned or n["pitch"] != cleaned[-1]["pitch"] or n["start"] >= cleaned[-1]["end"]:
            cleaned.append(dict(n))
        else:
            cleaned[-1]["end"] = max(cleaned[-1]["end"], n["end"])
            cleaned[-1]["velocity"] = max(cleaned[-1]["velocity"], n["velocity"])
            report["merged_overlaps"] += 1
    report["kept_notes"] = len(cleaned)
    return cleaned, report


def _isolated(note: dict[str, Any], others: list[dict[str, Any]], window: float, gap: int) -> bool:
    nearest = None
    for m in others:
        if m is note:
            continue
        if abs(m["start"] - note["start"]) <= window:
            d = abs(m["pitch"] - note["pitch"])
            if nearest is None or d < nearest:
                nearest = d
    return nearest is not None and nearest > gap


def cleanup_model_score(
    notes: list[dict[str, Any]], amplitude_threshold: float = 0.3, **_: Any
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    kept = [n for n in notes if n.get("amplitude", 1.0) >= amplitude_threshold]
    report = {
        "profile": "model_score",
        "input_notes": len(notes),
        "kept_notes": len(kept),
        "removed_weak": len(notes) - len(kept),
        "amplitude_threshold": amplitude_threshold,
    }
    return kept, report


def cleanup_model_context(
    notes: list[dict[str, Any]],
    amplitude_threshold: float = 0.3,
    min_duration: float = 0.1,
    isolation_window: float = 0.5,
    isolation_gap: int = 12,
    high_register: int = 96,
    **_: Any,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Model score + conservative context filtering.

    Drops a note when it has weak model evidence OR is a very short fragment OR
    is pitch-isolated far from its neighbors OR is an isolated extreme-register
    event.  Never drops by a hard pitch-only rule.
    """
    report = {
        "profile": "model_context",
        "input_notes": len(notes),
        "removed_weak": 0,
        "removed_short": 0,
        "removed_isolated": 0,
        "removed_extreme_isolated": 0,
        "amplitude_threshold": amplitude_threshold,
    }
    kept: list[dict[str, Any]] = []
    for n in notes:
        dur = n["end"] - n["start"]
        amp = n.get("amplitude", 1.0)
        extreme = n["pitch"] > high_register or n["pitch"] < 36
        isolated = _isolated(n, notes, isolation_window, isolation_gap)

        if amp < amplitude_threshold:
            report["removed_weak"] += 1
        elif dur < min_duration:
            report["removed_short"] += 1
        elif extreme and isolated:
            report["removed_extreme_isolated"] += 1
        elif isolated and amp < 0.5:
            report["removed_isolated"] += 1
        else:
            kept.append(n)
    report["kept_notes"] = len(kept)
    return kept, report


CONFIGS: dict[str, Any] = {
    "A_raw": cleanup_raw,
    "B_existing": cleanup_existing,
    "C_model_score": cleanup_model_score,
    "D_model_context": cleanup_model_context,
}
