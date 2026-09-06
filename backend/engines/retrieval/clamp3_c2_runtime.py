"""Child runtime for CLaMP3 C2 text-to-performance passage retrieval.

The normal ListenCloser process never imports Torch/Transformers/CLaMP3. This
module runs inside a separately provisioned Python environment with pinned local
assets. It converts fixed performance-time MIDI windows to upstream-compatible
MIDI Text Format (MTF), embeds them with CLaMP3 C2, and writes one bounded JSON
result.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
from dataclasses import dataclass
from pathlib import Path

_EXCLUDED_M3_META_TYPES = {
    "text",
    "copyright",
    "track_name",
    "instrument_name",
    "lyrics",
    "marker",
    "cue_marker",
    "device_name",
}


@dataclass(frozen=True)
class _TimedMidiEvent:
    seconds: float
    ticks: int
    message: object


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkout", required=True)
    parser.add_argument("--weights", required=True)
    parser.add_argument("--text-model", required=True)
    parser.add_argument("--midi", required=True)
    parser.add_argument("--query", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--window-seconds", required=True, type=float)
    parser.add_argument("--hop-seconds", required=True, type=float)
    parser.add_argument("--max-matches", required=True, type=int)
    return parser


def _normalized(vector):
    import torch

    vector = vector.reshape(-1).float()
    norm = torch.linalg.vector_norm(vector)
    if not torch.isfinite(norm) or float(norm) <= 0:
        raise RuntimeError("CLaMP3 C2 produced a non-normalizable embedding")
    return vector / norm


def _window_starts(duration_seconds: float, window_seconds: float, hop_seconds: float) -> list[float]:
    if duration_seconds <= 0:
        return []
    if duration_seconds <= window_seconds:
        return [0.0]
    last_start = max(0.0, duration_seconds - window_seconds)
    starts: list[float] = []
    current = 0.0
    while current <= last_start + 1e-9:
        starts.append(current)
        current += hop_seconds
    if not math.isclose(starts[-1], last_start, abs_tol=1e-9):
        starts.append(last_start)
    return starts


def _overlap(a_start: float, a_end: float, b_start: float, b_end: float) -> bool:
    return min(a_end, b_end) > max(a_start, b_start)


def _timed_events(midi_path: str) -> tuple[int, list[_TimedMidiEvent], float]:
    import mido

    midi = mido.MidiFile(midi_path)
    tempo = 500_000
    absolute_seconds = 0.0
    absolute_ticks = 0
    events: list[_TimedMidiEvent] = []

    for message in mido.merge_tracks(midi.tracks):
        delta_ticks = int(message.time)
        absolute_ticks += delta_ticks
        absolute_seconds += float(mido.tick2second(delta_ticks, midi.ticks_per_beat, tempo))
        events.append(
            _TimedMidiEvent(
                seconds=absolute_seconds,
                ticks=absolute_ticks,
                message=message,
            )
        )
        if message.type == "set_tempo":
            tempo = int(message.tempo)

    return int(midi.ticks_per_beat), events, absolute_seconds


def _message_to_mtf(message) -> str:
    values = [str(value) for value in message.dict().values()]
    return " ".join(values).encode("unicode_escape").decode("utf-8")


def _window_to_mtf(
    ticks_per_beat: int,
    events: list[_TimedMidiEvent],
    *,
    start_seconds: float,
    end_seconds: float,
) -> str | None:
    selected = [event for event in events if start_seconds <= event.seconds < end_seconds]
    if not any(
        event.message.type == "note_on" and int(getattr(event.message, "velocity", 0)) > 0
        for event in selected
    ):
        return None

    lines = [f"ticks_per_beat {ticks_per_beat}"]
    previous_tick: int | None = None
    for event in selected:
        message = event.message
        if message.is_meta and message.type in _EXCLUDED_M3_META_TYPES:
            continue
        delta = 0 if previous_tick is None else max(0, event.ticks - previous_tick)
        previous_tick = event.ticks
        lines.append(_message_to_mtf(message.copy(time=delta)))

    return "\n".join(lines) if len(lines) > 1 else None


def _global_symbolic_embedding(model, patchilizer, mtf: str, clamp_config):
    import torch

    patches = patchilizer.encode(mtf, add_special_patches=True)
    if not patches:
        raise RuntimeError("CLaMP3 C2 MTF preprocessing produced no patches")

    max_length = int(clamp_config.PATCH_LENGTH)
    segment_embeddings = []
    weights = []
    for start in range(0, len(patches), max_length):
        segment = torch.tensor(patches[start : start + max_length])
        actual_length = int(segment.size(0))
        mask = torch.ones(actual_length, dtype=torch.float32)
        pad_count = max_length - actual_length
        if pad_count > 0:
            pad = torch.full(
                (pad_count, int(clamp_config.PATCH_SIZE)),
                patchilizer.pad_token_id,
                dtype=segment.dtype,
            )
            segment = torch.cat([segment, pad], dim=0)
            mask = torch.cat([mask, torch.zeros(pad_count)])
        with torch.no_grad():
            embedding = model.get_symbolic_features(
                symbolic_inputs=segment.unsqueeze(0),
                symbolic_masks=mask.unsqueeze(0),
                get_global=True,
            ).squeeze(0)
        segment_embeddings.append(embedding)
        weights.append(actual_length)

    stacked = torch.stack(segment_embeddings)
    weight_tensor = torch.tensor(weights, dtype=stacked.dtype).unsqueeze(1)
    return (stacked * weight_tensor).sum(dim=0) / weight_tensor.sum()


def main() -> int:
    args = _parser().parse_args()
    started = time.perf_counter()

    import torch
    from transformers import AutoTokenizer, BertConfig

    checkout = Path(args.checkout)
    code_dir = checkout / "code"
    if not code_dir.is_dir():
        raise RuntimeError("CLaMP3 checkout is missing code/")
    sys.path.insert(0, str(code_dir))

    import config as clamp_config  # type: ignore  # noqa: I001
    from utils import CLaMP3Model, M3Patchilizer  # type: ignore  # noqa: I001

    audio_config = BertConfig(
        vocab_size=1,
        hidden_size=clamp_config.AUDIO_HIDDEN_SIZE,
        num_hidden_layers=clamp_config.AUDIO_NUM_LAYERS,
        num_attention_heads=clamp_config.AUDIO_HIDDEN_SIZE // 64,
        intermediate_size=clamp_config.AUDIO_HIDDEN_SIZE * 4,
        max_position_embeddings=clamp_config.MAX_AUDIO_LENGTH,
    )
    symbolic_config = BertConfig(
        vocab_size=1,
        hidden_size=clamp_config.M3_HIDDEN_SIZE,
        num_hidden_layers=clamp_config.PATCH_NUM_LAYERS,
        num_attention_heads=clamp_config.M3_HIDDEN_SIZE // 64,
        intermediate_size=clamp_config.M3_HIDDEN_SIZE * 4,
        max_position_embeddings=clamp_config.PATCH_LENGTH,
    )
    model = CLaMP3Model(
        audio_config=audio_config,
        symbolic_config=symbolic_config,
        text_model_name=str(Path(args.text_model)),
        hidden_size=clamp_config.CLAMP3_HIDDEN_SIZE,
        load_m3=False,
    )
    checkpoint = torch.load(args.weights, map_location="cpu", weights_only=True)
    if not isinstance(checkpoint, dict) or "model" not in checkpoint:
        raise RuntimeError("CLaMP3 C2 checkpoint payload is missing model weights")
    model.load_state_dict(checkpoint["model"])
    model.eval()

    tokenizer = AutoTokenizer.from_pretrained(args.text_model, local_files_only=True)
    patchilizer = M3Patchilizer()

    query = Path(args.query).read_text(encoding="utf-8").strip()
    if not query:
        raise RuntimeError("query text is empty")

    text_tokens = tokenizer(query, return_tensors="pt")["input_ids"].squeeze(0)
    max_text_length = int(clamp_config.MAX_TEXT_LENGTH)
    text_segment = text_tokens[:max_text_length]
    text_mask = torch.ones(text_segment.size(0), dtype=torch.float32)
    text_pad = max_text_length - text_segment.size(0)
    if text_pad > 0:
        text_segment = torch.cat(
            [
                text_segment,
                torch.full(
                    (text_pad,), tokenizer.pad_token_id, dtype=text_segment.dtype
                ),
            ]
        )
        text_mask = torch.cat([text_mask, torch.zeros(text_pad)])
    with torch.no_grad():
        query_embedding = model.get_text_features(
            text_inputs=text_segment.unsqueeze(0),
            text_masks=text_mask.unsqueeze(0),
            get_global=True,
        )
    query_embedding = _normalized(query_embedding.squeeze(0))

    ticks_per_beat, events, duration_seconds = _timed_events(args.midi)
    if duration_seconds <= 0:
        raise RuntimeError("performance MIDI has zero duration")

    scored: list[dict[str, float]] = []
    embedding_dim = 0
    for start_seconds in _window_starts(
        duration_seconds, args.window_seconds, args.hop_seconds
    ):
        end_seconds = min(duration_seconds, start_seconds + args.window_seconds)
        mtf = _window_to_mtf(
            ticks_per_beat,
            events,
            start_seconds=start_seconds,
            end_seconds=end_seconds + 1e-9,
        )
        if mtf is None:
            continue
        with torch.no_grad():
            symbolic_embedding = _global_symbolic_embedding(
                model, patchilizer, mtf, clamp_config
            )
        symbolic_embedding = _normalized(symbolic_embedding)
        embedding_dim = int(symbolic_embedding.numel())
        if embedding_dim != int(query_embedding.numel()):
            raise RuntimeError("CLaMP3 C2 text/symbolic embedding dimensions do not match")
        similarity = float(torch.dot(query_embedding, symbolic_embedding))
        if not math.isfinite(similarity):
            raise RuntimeError("CLaMP3 C2 produced a non-finite similarity")
        scored.append(
            {
                "start_seconds": start_seconds,
                "end_seconds": end_seconds,
                "similarity": max(-1.0, min(1.0, similarity)),
            }
        )

    scored.sort(key=lambda item: (-item["similarity"], item["start_seconds"]))
    selected: list[dict[str, float]] = []
    for candidate in scored:
        if any(
            _overlap(
                candidate["start_seconds"],
                candidate["end_seconds"],
                existing["start_seconds"],
                existing["end_seconds"],
            )
            for existing in selected
        ):
            continue
        selected.append(candidate)
        if len(selected) >= args.max_matches:
            break

    payload = {
        "candidates": selected,
        "embedding_dim": embedding_dim,
        "duration_seconds": duration_seconds,
        "runtime_seconds": time.perf_counter() - started,
    }
    Path(args.output).write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
