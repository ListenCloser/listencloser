"""Scored solo-piano bakeoff on the prepared real-world corpus.

Runs the transcription engines (Basic Pitch, Transkun, piano_transcription)
over the prepared MAESTRO solo-piano clips and writes a per-clip scored report.

  python -m evaluation.reports.solo_piano_bakeoff --corpus real_world_v1

Writes machine-readable JSON + Markdown to evaluation/reports/.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

from evaluation.datasets import cache
from evaluation.transcription_metrics import Note, compute_note_metrics

_ONSET = 0.5
_FRAME = 0.3


def _prepared_dir(corpus: str) -> Path:
    return cache.cache_dir() / "prepared" / corpus


def _load_prepared(corpus: str) -> list[dict[str, Any]]:
    summary_path = cache.cache_dir() / f"prepared-{corpus}.json"
    with open(summary_path) as fh:
        summary = json.load(fh)
    return [c for c in summary["clips"] if c["status"] == "ok"]


def _reference_notes(prepared_dir: Path, clip_id: str) -> list[Note]:
    midi_path = prepared_dir / f"{clip_id}.mid"
    if not midi_path.exists():
        return []
    import pretty_midi

    pm = pretty_midi.PrettyMIDI(str(midi_path))
    return [
        Note(pitch=n.pitch, start=n.start, end=n.end, velocity=n.velocity)
        for inst in pm.instruments
        for n in inst.notes
        if not inst.is_drum
    ]


def _transcribe(engine: str, audio_bytes: bytes) -> dict[str, Any]:
    import sys

    backend_dir = str(Path(__file__).resolve().parent.parent.parent)
    if backend_dir not in sys.path:
        sys.path.insert(0, backend_dir)
    from evaluation.engines.transcription import get_transcription_adapter

    adapter = get_transcription_adapter(engine)
    result = adapter.transcribe(audio_bytes)
    notes: list[Note] = []
    for note in result["notes"]:
        notes.append(
            Note(
                pitch=int(note["pitch"]),
                start=float(note["start"]),
                end=float(note["end"]),
                velocity=int(note.get("velocity", 64)),
            )
        )
    return {"notes": notes, "duration_s": float(result.get("duration_s", 0.0))}


def _metric_block(pred: list[Note], ref: list[Note]) -> dict[str, Any] | None:
    if not ref:
        return None
    m = compute_note_metrics(pred, ref)
    d = m.to_dict()
    d["excessive_rate"] = round(m.excessive_count / max(m.predicted_count, 1), 4)
    d["missed_rate"] = round(m.missed_count / max(m.reference_count, 1), 4)
    return d


def run(corpus: str, engines: list[str], output_dir: str) -> dict[str, Any]:
    prepared_dir = _prepared_dir(corpus)
    clips = _load_prepared(corpus)
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    rows: list[dict[str, Any]] = []
    for clip in clips:
        clip_id = clip["id"]
        audio_path = prepared_dir / f"{clip_id}.wav"
        ref = _reference_notes(prepared_dir, clip_id)
        if not audio_path.exists():
            rows.append({"id": clip_id, "status": "missing", "category": clip.get("category")})
            continue
        for engine in engines:
            t0 = time.time()
            try:
                tr = _transcribe(engine, audio_path.read_bytes())
                runtime = round(time.time() - t0, 2)
            except Exception as exc:  # noqa: BLE001
                rows.append(
                    {
                        "id": clip_id,
                        "engine": engine,
                        "status": "error",
                        "message": str(exc),
                    }
                )
                continue
            pred = tr["notes"]
            metrics = _metric_block(pred, ref)
            rows.append(
                {
                    "id": clip_id,
                    "engine": engine,
                    "status": "ok",
                    "category": clip.get("category"),
                    "predicted_count": len(pred),
                    "reference_count": len(ref),
                    "runtime_s": runtime,
                    "metrics": metrics,
                }
            )

    payload = {"corpus": corpus, "engines": engines, "rows": rows}
    json_path = out / "solo_piano_bakeoff.json"
    json_path.write_text(json.dumps(payload, indent=2))
    md_path = out / "solo_piano_bakeoff.md"
    md_path.write_text(_render_markdown(payload))
    print(f"wrote {json_path}\nwrote {md_path}")
    return payload


def _render_markdown(payload: dict[str, Any]) -> str:
    rows = payload["rows"]
    lines = [f"# Scored solo-piano bakeoff: {payload['corpus']}", ""]
    for engine in payload["engines"]:
        lines.append(f"## {engine}")
        lines.append("| Clip | Ref | Pred | Note F1 | Onset F1 | Prec | Recall | Err | Missed |")
        lines.append("|------|-----|------|---------|----------|------|--------|-----|--------|")
        for r in rows:
            if r.get("engine") != engine:
                continue
            if r["status"] != "ok" or r["metrics"] is None:
                lines.append(
                    f"| {r['id']} | {r.get('reference_count', '-')} | "
                    f"{r.get('predicted_count', '-')} | - | - | - | - | - | - |"
                )
                continue
            m = r["metrics"]
            lines.append(
                f"| {r['id']} | {r['reference_count']} | {r['predicted_count']} "
                f"| {m['note_f1']:.4f} | {m['onset_f1']:.4f} | {m['note_precision']:.4f} "
                f"| {m['note_recall']:.4f} | {m['excessive_rate']:.4f} | {m['missed_rate']:.4f} |"
            )
        lines.append("")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Scored solo-piano bakeoff")
    parser.add_argument("--corpus", default="real_world_v1")
    parser.add_argument(
        "--engines",
        nargs="+",
        default=["basic_pitch", "transkun", "piano_transcription"],
    )
    parser.add_argument("--output", default="evaluation/reports")
    args = parser.parse_args()
    run(args.corpus, args.engines, args.output)


if __name__ == "__main__":
    main()
