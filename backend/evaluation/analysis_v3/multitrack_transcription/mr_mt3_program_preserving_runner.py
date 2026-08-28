"""Research-only MR-MT3 runner that preserves decoded program tokens.

mt3-infer 0.2.0's pinned MR-MT3 adapter correctly decodes program events into
``vocab_utils.Note.program`` but its final ``mido.MidiFile`` serializer drops
that field and emits all pitched notes on channel 0 without program changes.
That serializer is unsuitable for #337's instrument-aware evaluation.

This runner leaves the model, checkpoint, preprocessing, forward pass, codec,
and note-state decoder untouched. It only serializes the already-decoded
``NoteSequence`` into program-separated PrettyMIDI instruments so the frozen
hello-ai scorer can evaluate the model's actual program predictions.
"""

from __future__ import annotations

import argparse
import json
import time
from collections import defaultdict
from pathlib import Path

import pretty_midi

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


def _write_program_midi(note_sequence, output: Path) -> list[dict[str, object]]:
    grouped = defaultdict(list)
    for note in note_sequence.notes:
        key = (0 if note.is_drum else int(note.program), bool(note.is_drum))
        grouped[key].append(note)

    midi = pretty_midi.PrettyMIDI(initial_tempo=120.0)
    streams: list[dict[str, object]] = []
    for (program, is_drum), notes in sorted(grouped.items(), key=lambda item: (item[0][1], item[0][0])):
        instrument = pretty_midi.Instrument(
            program=program,
            is_drum=is_drum,
            name="MR-MT3 drums" if is_drum else f"MR-MT3 program {program}",
        )
        for note in notes:
            instrument.notes.append(
                pretty_midi.Note(
                    velocity=max(1, min(127, int(note.velocity))),
                    pitch=max(0, min(127, int(note.pitch))),
                    start=max(0.0, float(note.start_time)),
                    end=max(float(note.start_time) + 0.001, float(note.end_time)),
                )
            )
        midi.instruments.append(instrument)
        streams.append(
            {
                "program": program,
                "is_drum": is_drum,
                "notes": len(notes),
            }
        )

    output.parent.mkdir(parents=True, exist_ok=True)
    midi.write(str(output))
    return streams


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
        output_path = Path(job["output"])

        audio_started = time.perf_counter()
        audio, sample_rate = load_audio(str(audio_path), sr=16000)
        audio_load_seconds = time.perf_counter() - audio_started

        inference_started = time.perf_counter()
        features = model.preprocess(audio, sample_rate)
        outputs = model.forward(features)
        note_sequence, invalid_events, dropped_events = _decode_note_sequence(model, outputs)
        streams = _write_program_midi(note_sequence, output_path)
        inference_decode_seconds = time.perf_counter() - inference_started

        results.append(
            {
                "id": track_id,
                "audio": str(audio_path),
                "output": str(output_path),
                "audio_load_seconds": round(audio_load_seconds, 3),
                "inference_decode_seconds": round(inference_decode_seconds, 3),
                "predicted_notes": sum(int(stream["notes"]) for stream in streams),
                "predicted_streams": streams,
                "invalid_events": int(invalid_events),
                "dropped_events": int(dropped_events),
            }
        )

    payload = {
        "serializer": "hello-ai research program-preserving serializer",
        "model_load_seconds": round(model_load_seconds, 3),
        "tracks": results,
    }
    Path(args.stats).write_text(json.dumps(payload, indent=2) + "\n")
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
