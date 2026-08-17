"""Harmony feasibility / baseline scoring against GuitarSet JAMS ground truth.

Scores the existing production music21 symbolic harmony path against
GuitarSet's real guitar chord + key annotations. This is an EVALUATION-ONLY
script: it does not alter production behavior.

Pipeline per clip:
  1. Read the cached GuitarSet JAMS annotation (audio already prepared).
  2. Extract the harmony reference (chords + key) via ``parse_guitarset_harmony``.
  3. Build a reference MIDI from the JAMS ``note_midi`` annotations via
     ``build_guitarset_reference_midi`` (GuitarSet ships no reference MIDI).
  4. Run the production ``Music21HarmonyAdapter.analyze_harmony`` on that MIDI.
  5. Score chord precision/recall/F1 (±0.5s root window) and key accuracy via
     the shared ``compute_analysis_metrics``.

Usage:
  python -m evaluation.harmony_feasibility
"""

from __future__ import annotations

import glob
import json
from pathlib import Path
from typing import Any

from evaluation.analysis_metrics import compute_analysis_metrics
from evaluation.datasets.parsers import (
    build_guitarset_reference_midi,
    parse_guitarset_harmony,
    parse_guitarset_jams,
)
from evaluation.engines.harmony import get_harmony_adapter
from evaluation.models import Reference

_ANNOTATION_GLOB = "evaluation/.cache/guitarset/annotation/*.jams"


def _reference_from_harmony(harmony: dict[str, Any]) -> Reference:
    ref = Reference()
    key = harmony.get("key", {})
    if key.get("tonic") and key.get("mode"):
        ref.key = f"{key['tonic']} {key['mode']}"
    ref.chords = [
        {"root": c["root"], "quality": c.get("quality", ""), "start": c["start"], "end": c["end"]}
        for c in harmony.get("chords", [])
    ]
    return ref


def _predicted_key_from_music21(output: dict[str, Any]) -> str | None:
    key = output.get("key") or {}
    tonic = key.get("tonic")
    mode = key.get("mode")
    if not tonic or not mode:
        return None
    return f"{tonic} {mode}"


def _normalize_key_label(label: str) -> str:
    """Normalize music21's flat spelling (``E-``) to ``Eb`` for comparison."""
    import re

    def _sub(match: re.Match) -> str:
        return match.group(0).replace("-", "b")

    return re.sub(r"[A-G]-", _sub, label)


def _diagnostic_chords(midi_bytes: bytes) -> list[dict[str, Any]]:
    """DIAGNOSTIC-ONLY chord extraction using music21's always-available
    ``ch.quality`` (the production adapter's ``impliedQuality`` is absent on
    MIDI-derived chords, so it emits zero chords). This documents what the
    same library could produce with a different extraction — it is NOT the
    production behavior and is not used for the scored baseline."""
    import os
    import tempfile

    from music21 import converter

    with tempfile.NamedTemporaryFile(suffix=".mid", delete=False) as f:
        f.write(midi_bytes)
        temp_path = f.name
    try:
        score = converter.parse(temp_path)
    finally:
        os.unlink(temp_path)
    chords: list[dict[str, Any]] = []
    for ch in score.flatten().getElementsByClass("Chord"):
        try:
            root = ch.root()
            if root is None:
                continue
            start = float(ch.getOffsetInHierarchy(score))
            dur = float(ch.quarterLength) if hasattr(ch, "quarterLength") else 0.0
            if dur <= 0:
                continue
            chords.append(
                {
                    "root": root.name,
                    "quality": str(ch.quality),
                    "start": round(start, 3),
                    "end": round(start + dur, 3),
                }
            )
        except Exception:
            continue
    return chords


def run_feasibility() -> list[dict[str, Any]]:
    adapter = get_harmony_adapter("music21_symbolic")
    if not adapter.is_available():
        raise RuntimeError("music21 not available")

    rows: list[dict[str, Any]] = []
    for path in sorted(glob.glob(_ANNOTATION_GLOB)):
        clip_id = Path(path).stem  # e.g. 00_BN1-129-Eb_comp
        jams = Path(path).read_text()
        harmony = parse_guitarset_harmony(jams)
        notes = parse_guitarset_jams(jams)
        reference = _reference_from_harmony(harmony)
        midi_bytes = build_guitarset_reference_midi(notes)

        row: dict[str, Any] = {
            "clip_id": clip_id,
            "key_reference": harmony["key"].get("label"),
            "chord_reference_count": len(harmony["chords"]),
            "note_reference_count": len(notes),
        }
        try:
            output = adapter.analyze_harmony(midi_bytes)
            predicted_key = _predicted_key_from_music21(output)
            predicted_key_normalized = (
                _normalize_key_label(predicted_key) if predicted_key else None
            )
            predicted_chords = [
                {"root": c["root"], "quality": c["quality"], "start": c["start"], "end": c["end"]}
                for c in output.get("chords", [])
            ]
            diagnostic_chords = _diagnostic_chords(midi_bytes)
            row["music21_key"] = predicted_key
            row["music21_key_normalized"] = predicted_key_normalized
            row["music21_chord_count"] = len(predicted_chords)
            row["music21_chords"] = predicted_chords
            row["diagnostic_chord_count"] = len(diagnostic_chords)
            row["diagnostic_chords"] = diagnostic_chords
            metrics = compute_analysis_metrics(
                predicted_key=predicted_key_normalized,
                predicted_bpm=0.0,
                predicted_meter=None,
                predicted_sections=None,
                predicted_chords=predicted_chords,
                reference=reference,
            )
            row["metrics"] = metrics.to_dict()
            row["status"] = "ok"
        except Exception as exc:
            row["status"] = "error"
            row["message"] = str(exc)
        rows.append(row)
    return rows


def _score_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    scored = [r for r in rows if r.get("status") == "ok" and r.get("metrics")]
    key_vals = [
        r["metrics"].get("key_correct")
        for r in scored
        if r["metrics"].get("key_correct") is not None
    ]
    chord_p = [
        r["metrics"]["chord_precision"]
        for r in scored
        if r["metrics"].get("chord_precision") is not None
    ]
    chord_r = [
        r["metrics"]["chord_recall"] for r in scored if r["metrics"].get("chord_recall") is not None
    ]
    chord_f1 = [
        r["metrics"]["chord_f1"] for r in scored if r["metrics"].get("chord_f1") is not None
    ]
    return {
        "clips_total": len(rows),
        "scored": len(scored),
        "failed": sum(1 for r in rows if r["status"] != "ok"),
        "key_accuracy": round(sum(key_vals) / len(key_vals), 4) if key_vals else None,
        "chord_precision_macro": round(sum(chord_p) / len(chord_p), 4) if chord_p else None,
        "chord_recall_macro": round(sum(chord_r) / len(chord_r), 4) if chord_r else None,
        "chord_f1_macro": round(sum(chord_f1) / len(chord_f1), 4) if chord_f1 else None,
    }


def main() -> None:
    rows = run_feasibility()
    summary = _score_summary(rows)
    print(json.dumps(summary, indent=2))
    for r in rows:
        if r.get("status") == "ok":
            m = r.get("metrics") or {}
            norm_key = r.get("music21_key_normalized")
            print(
                f"{r['clip_id']}: key={r.get('music21_key')} (norm {norm_key}, "
                f"ref {r.get('key_reference')}) chords={r.get('music21_chord_count')}/"
                f"{r.get('chord_reference_count')} (diag {r.get('diagnostic_chord_count')}) "
                f"chordF1={m.get('chord_f1')} keyOK={m.get('key_correct')}"
            )
        else:
            print(f"{r['clip_id']}: ERROR {r.get('message')}")


if __name__ == "__main__":
    main()
