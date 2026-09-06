"""Child-runtime bridge for bounded CLaMP3 text-to-passage retrieval.

This module intentionally has no ListenCloser imports. It is executed by a
separately provisioned Python environment containing the upstream CLaMP3/MERT
runtime and writes one small JSON payload for the normal API process.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
from pathlib import Path


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkout", required=True)
    parser.add_argument("--weights", required=True)
    parser.add_argument("--mert-model", required=True)
    parser.add_argument("--text-model", required=True)
    parser.add_argument("--audio", required=True)
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
        raise RuntimeError("CLaMP3 produced a non-normalizable embedding")
    return vector / norm


def _window_starts(total_samples: int, window_samples: int, hop_samples: int) -> list[int]:
    if total_samples <= 0:
        return []
    if total_samples <= window_samples:
        return [0]
    last_start = total_samples - window_samples
    starts = list(range(0, last_start + 1, hop_samples))
    if starts[-1] != last_start:
        starts.append(last_start)
    return starts


def _overlap(a_start: float, a_end: float, b_start: float, b_end: float) -> bool:
    return min(a_end, b_end) > max(a_start, b_start)


def main() -> int:
    args = _parser().parse_args()
    started = time.perf_counter()

    import torch
    import torchaudio
    from transformers import AutoFeatureExtractor, AutoModel, AutoTokenizer, BertConfig

    checkout = Path(args.checkout)
    code_dir = checkout / "code"
    if not code_dir.is_dir():
        raise RuntimeError("CLaMP3 checkout is missing code/")
    sys.path.insert(0, str(code_dir))

    import config as clamp_config  # type: ignore  # noqa: I001
    from utils import CLaMP3Model  # type: ignore  # noqa: I001

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
        load_m3=clamp_config.CLAMP3_LOAD_M3,
    )
    checkpoint = torch.load(args.weights, map_location="cpu", weights_only=True)
    if not isinstance(checkpoint, dict) or "model" not in checkpoint:
        raise RuntimeError("CLaMP3 checkpoint payload is missing model weights")
    model.load_state_dict(checkpoint["model"])
    model.eval()

    tokenizer = AutoTokenizer.from_pretrained(
        args.text_model,
        local_files_only=True,
    )
    mert_processor = AutoFeatureExtractor.from_pretrained(
        args.mert_model,
        trust_remote_code=True,
        local_files_only=True,
    )
    mert_model = AutoModel.from_pretrained(
        args.mert_model,
        trust_remote_code=True,
        local_files_only=True,
    )
    mert_model.eval()

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
                    (text_pad,),
                    tokenizer.pad_token_id,
                    dtype=text_segment.dtype,
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

    waveform, sample_rate = torchaudio.load(args.audio)
    if sample_rate != 24000:
        raise RuntimeError(f"normalized audio sample rate is {sample_rate}, expected 24000")
    if waveform.ndim != 2 or waveform.size(0) != 1:
        raise RuntimeError("normalized audio must be mono")
    waveform = waveform.squeeze(0).float()
    total_samples = int(waveform.numel())
    duration_seconds = total_samples / float(sample_rate)
    if duration_seconds <= 0:
        raise RuntimeError("normalized audio has zero duration")

    window_samples = max(1, int(round(args.window_seconds * sample_rate)))
    hop_samples = max(1, int(round(args.hop_seconds * sample_rate)))
    starts = _window_starts(total_samples, window_samples, hop_samples)
    scored: list[dict[str, float]] = []
    embedding_dim = 0

    for start_sample in starts:
        end_sample = min(total_samples, start_sample + window_samples)
        segment = waveform[start_sample:end_sample]
        if segment.numel() == 0:
            continue
        processor_inputs = mert_processor(
            segment.numpy(),
            sampling_rate=sample_rate,
            return_tensors="pt",
            padding=True,
        )
        with torch.no_grad():
            mert_output = mert_model(**processor_inputs)
        features = mert_output.last_hidden_state.squeeze(0).float()
        if features.ndim != 2 or features.size(0) == 0:
            raise RuntimeError("MERT produced invalid audio features")

        max_audio_length = int(clamp_config.MAX_AUDIO_LENGTH)
        if features.size(0) > max_audio_length:
            features = features[:max_audio_length]
        audio_mask = torch.ones(features.size(0), dtype=torch.float32)
        audio_pad = max_audio_length - features.size(0)
        if audio_pad > 0:
            features = torch.cat(
                [features, torch.zeros(audio_pad, features.size(1), dtype=features.dtype)],
                dim=0,
            )
            audio_mask = torch.cat([audio_mask, torch.zeros(audio_pad)])

        with torch.no_grad():
            audio_embedding = model.get_audio_features(
                audio_inputs=features.unsqueeze(0),
                audio_masks=audio_mask.unsqueeze(0),
                get_global=True,
            )
        audio_embedding = _normalized(audio_embedding.squeeze(0))
        embedding_dim = int(audio_embedding.numel())
        if embedding_dim != int(query_embedding.numel()):
            raise RuntimeError("CLaMP3 text/audio embedding dimensions do not match")
        similarity = float(torch.dot(query_embedding, audio_embedding))
        if not math.isfinite(similarity):
            raise RuntimeError("CLaMP3 produced a non-finite similarity")
        scored.append(
            {
                "start_seconds": start_sample / float(sample_rate),
                "end_seconds": end_sample / float(sample_rate),
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
