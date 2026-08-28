"""Research-only MR-MT3 runner that preserves decoded program tokens.

mt3-infer 0.2.0's pinned MR-MT3 adapter correctly decodes program events into
``vocab_utils.Note.program`` but its final ``mido.MidiFile`` serializer drops
that field and emits all pitched notes on channel 0 without program changes.
That serializer is unsuitable for #337's instrument-aware evaluation.

This runner leaves the model, checkpoint, preprocessing, forward pass, codec,
and note-state decoder untouched. To avoid introducing candidate-environment
MIDI serialization dependencies, it emits the already-decoded notes as JSON.
The trusted hello-ai evaluation environment then serializes those notes to MIDI
for the frozen scorer.
"""

from __future__ import annotations

import argparse
import json
import time
from collections import Counter
from pathlib import Path

from mt3_infer import load_model
from mt3_infer.adapters import vocab_utils
from mt3_infer.utils.audio import load_audio


def _decode_note_sequence(model, outputs):
    predictions = []
    for batch_tokens, batch_frame_times in zip(outputs["tokens"], outputs["frame_times"]):
        valid_tokens = batch_tokens[batch_tokens >= 0]
        if len(valid_tokens):
            predictions.append(
                {
                    "est_tokens": valid_tokens,
                    "start_time": float(batch_frame_times[0]),
                }
            )
    return vocab_utils.decode_and_combine_predictions(predictions, model.codec)


def _serialize_notes(note_sequence) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    notes = [
        {
            "pitch": int(note.pitch),
            "start_time": float(note.start_time),
            "end_time": float(note.end_time),
            "velocity": int(note.velocity),
            "program": 0 if note.is_drum else int(note.program),
            "is_drum": bool(note.is_drum),
        }
        for note in note_sequence.notes
    ]
    counts = Counter((int(note["program"]), bool(note["is_drum"])) for note in notes)
    streams = [
        {"program": program, "is_drum": is_drum, "notes": count}
        for (program, is_drum), count in sorted(counts.items(), key=lambda item: (item[0][1], item[0][0]))
    ]
    return notes, streams


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkpoint", required=True)
    parser.add_argument("--jobs-json", required=True)
    parser.add_argument("--stats", required=True)
    args = parser.parse_args()

    jobs = json.loads(Path(args.jobs_json).read_text())
    if not isinstance(jobs, list) or not jobs:
        raise ValueError("jobs-json must contain a non-empty list")

    model_started = time.perf_counter()
    model = load_model(
        "mr_mt3",
        checkpoint_path=args.checkpoint,
        device="cpu",
        cache=False,
        auto_download=False,
    )
    model_load_seconds = time.perf_counter() - model_started

    results: list[dict[str, object]] = []
    for job in jobs:
        track_id = str(job["id"])
        audio_path = Path(job["audio"])
        output_json = Path(job["output_json"])

        audio_started = time.perf_counter()
        audio, sample_rate = load_audio(str(audio_path), sr=16000)
        audio_load_seconds = time.perf_counter() - audio_started

        inference_started = time.perf_counter()
        features = model.preprocess(audio, sample_rate)
        outputs = model.forward(features)
        note_sequence, invalid_events, dropped_events = _decode_note_sequence(model, outputs)
        notes, streams = _serialize_notes(note_sequence)
        inference_decode_seconds = time.perf_counter() - inference_started

        output_json.parent.mkdir(parents=True, exist_ok=True)
        output_json.write_text(json.dumps({"id": track_id, "notes": notes}, indent=2) + "\n")
        results.append(
            {
                "id": track_id,
                "audio": str(audio_path),
                "output_json": str(output_json),
                "audio_load_seconds": round(audio_load_seconds, 3),
                "inference_decode_seconds": round(inference_decode_seconds, 3),
                "predicted_notes": len(notes),
                "predicted_streams": streams,
                "invalid_events": int(invalid_events),
                "dropped_events": int(dropped_events),
            }
        )

    payload = {
        "serializer": "decoded-note JSON; MIDI serialization deferred to hello-ai evaluator",
        "model_load_seconds": round(model_load_seconds, 3),
        "tracks": results,
    }
    Path(args.stats).write_text(json.dumps(payload, indent=2) + "\n")
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
