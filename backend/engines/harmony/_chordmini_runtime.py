"""Minimal ChordMini 2E1D inference runtime.

This module ports only the inference pieces required by ListenCloser from
ptnghia-j/ChordMini at commit aa6e3a8d7b017f082fd2aaff9329d5c26af49c03.
The upstream source is MIT licensed. The model checkpoint is not vendored here;
operators must provide the exact pinned checkpoint through the engine adapter.

The implementation intentionally follows upstream inference semantics:
22.05 kHz mono audio -> 144-bin CQT -> log magnitude -> checkpoint
normalization -> overlapping ChordNet windows -> frame voting -> contiguous
170-class chord segments.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

UPSTREAM_REPOSITORY = "ptnghia-j/ChordMini"
UPSTREAM_COMMIT = "aa6e3a8d7b017f082fd2aaff9329d5c26af49c03"
CHECKPOINT_NAME = "2e1d_model_best.pth"
CHECKPOINT_GIT_BLOB_SHA = "b61f6b3a02cc42b87afa38392f80d185a49f719a"
CHECKPOINT_SIZE = 27_523_646
SAMPLE_RATE = 22_050
HOP_LENGTH = 2_048
N_BINS = 144
BINS_PER_OCTAVE = 24
N_CLASSES = 170
SEQ_LEN = 108
OVERLAP_RATIO = 0.5
BATCH_SIZE = 16
SMOOTH_KERNEL_SIZE = 9


@dataclass(frozen=True)
class ChordMiniInferenceResult:
    segments: list[tuple[float, float, str]]
    checkpoint_sha256: str
    frame_duration: float
    frame_count: int


def _git_blob_sha(data: bytes) -> str:
    header = f"blob {len(data)}\0".encode()
    return hashlib.sha1(header + data, usedforsecurity=False).hexdigest()


def validate_checkpoint(path: str | Path) -> tuple[bytes, str]:
    checkpoint_path = Path(path)
    if not checkpoint_path.is_file():
        raise RuntimeError(
            "ChordMini checkpoint is unavailable. Set CHORDMINI_CHECKPOINT_PATH "
            f"to the pinned {CHECKPOINT_NAME} artifact."
        )

    data = checkpoint_path.read_bytes()
    if len(data) != CHECKPOINT_SIZE:
        raise RuntimeError(
            "ChordMini checkpoint size does not match the pinned upstream artifact: "
            f"expected {CHECKPOINT_SIZE}, got {len(data)}"
        )

    git_blob_sha = _git_blob_sha(data)
    if git_blob_sha != CHECKPOINT_GIT_BLOB_SHA:
        raise RuntimeError(
            "ChordMini checkpoint identity mismatch: "
            f"expected git blob {CHECKPOINT_GIT_BLOB_SHA}, got {git_blob_sha}"
        )

    return data, hashlib.sha256(data).hexdigest()


def _idx_to_chord() -> dict[int, str]:
    pitch_classes = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
    qualities = [
        "min",
        "maj",
        "dim",
        "aug",
        "min6",
        "maj6",
        "min7",
        "minmaj7",
        "maj7",
        "7",
        "dim7",
        "hdim7",
        "sus2",
        "sus4",
    ]
    mapping: dict[int, str] = {}
    for root_idx, root in enumerate(pitch_classes):
        for quality_idx, quality in enumerate(qualities):
            idx = root_idx * len(qualities) + quality_idx
            mapping[idx] = root if quality == "maj" else f"{root}:{quality}"
    mapping[168] = "X"
    mapping[169] = "N"
    return mapping


def _extract_state_dict(checkpoint: dict[str, Any]) -> dict[str, Any]:
    state_dict = checkpoint.get("model_state_dict", checkpoint.get("model", checkpoint))
    if not isinstance(state_dict, dict) or not state_dict:
        raise RuntimeError("ChordMini checkpoint does not contain a model state dictionary")
    if next(iter(state_dict)).startswith("module."):
        state_dict = {key.removeprefix("module."): value for key, value in state_dict.items()}
    return state_dict


def _normalization_stats(checkpoint: dict[str, Any]) -> tuple[float, float]:
    mean = checkpoint.get("mean", 0.0)
    std = checkpoint.get("std", 1.0)
    normalization = checkpoint.get("normalization")
    if isinstance(normalization, dict):
        mean = normalization.get("mean", mean)
        std = normalization.get("std", std)
    if hasattr(mean, "item"):
        mean = mean.item()
    if hasattr(std, "item"):
        std = std.item()
    return float(mean), max(float(std), 1e-8)


def _collect_layer_count(state_dict: dict[str, Any], prefix: str, marker: str) -> int | None:
    indices: set[int] = set()
    for key in state_dict:
        if prefix not in key:
            continue
        parts = key.split(".")
        for idx, part in enumerate(parts[:-1]):
            if part == marker and parts[idx + 1].isdigit():
                indices.add(int(parts[idx + 1]))
                break
    return max(indices) + 1 if indices else None


def _architecture(state_dict: dict[str, Any], checkpoint: dict[str, Any]) -> dict[str, Any]:
    params: dict[str, Any] = {
        "n_freq": N_BINS,
        "n_classes": N_CLASSES,
        "n_group": 12,
        "f_layer": 5,
        "f_head": 8,
        "t_layer": 5,
        "t_head": 8,
        "d_layer": 5,
        "d_head": 8,
        "dropout": 0.2,
    }
    fc_weight = state_dict.get("fc.weight")
    if fc_weight is not None:
        params["n_classes"] = int(fc_weight.shape[0])
        params["n_freq"] = int(fc_weight.shape[1])

    for key, value in state_dict.items():
        if "transformer.encoder_f.0.attn_layer.0.out_proj.weight" in key:
            feature_dim = int(value.shape[0])
            if feature_dim and params["n_freq"] % feature_dim == 0:
                params["n_group"] = params["n_freq"] // feature_dim
            break

    params["f_layer"] = _collect_layer_count(
        state_dict, "transformer.encoder_f.", "attn_layer"
    ) or params["f_layer"]
    params["t_layer"] = _collect_layer_count(
        state_dict, "transformer.encoder_t.", "attn_layer"
    ) or params["t_layer"]
    params["d_layer"] = _collect_layer_count(
        state_dict, "transformer.decoder.", "attn_layer1"
    ) or params["d_layer"]

    checkpoint_config = checkpoint.get("config")
    if isinstance(checkpoint_config, dict):
        for key in params:
            if key in checkpoint_config:
                params[key] = checkpoint_config[key]
    return params


def _build_model(state_dict: dict[str, Any], checkpoint: dict[str, Any], torch: Any) -> Any:
    nn = torch.nn
    functional = torch.nn.functional
    positional_cache: dict[tuple[int, int, bool, bool, Any], Any] = {}

    def positional_encoding(
        batch_size: int,
        n_time: int,
        n_feature: int,
        *,
        zero_pad: bool = False,
        scale: bool = False,
        dtype: Any = torch.float32,
    ) -> Any:
        cache_key = (n_time, n_feature, zero_pad, scale, dtype)
        if cache_key not in positional_cache:
            pos = torch.arange(n_time, dtype=dtype).reshape(-1, 1)
            frequencies = 2 * torch.arange(0, n_feature, dtype=dtype) / n_feature
            encoded = pos / torch.pow(10000, frequencies)
            encoded[:, 0::2] = torch.sin(encoded[:, 0::2])
            encoded[:, 1::2] = torch.cos(encoded[:, 1::2])
            if zero_pad:
                encoded = torch.cat([torch.zeros(1, n_feature), encoded[1:, :]], 0)
            if scale:
                encoded = encoded * (n_feature**0.5)
            positional_cache[cache_key] = encoded
        return positional_cache[cache_key].unsqueeze(0).expand(batch_size, -1, -1)

    class FeedForward(nn.Module):
        def __init__(self, n_feature: int, dropout: float) -> None:
            super().__init__()
            n_hidden = n_feature * 4
            self.linear1 = nn.Linear(n_feature, n_hidden)
            self.linear2 = nn.Linear(n_hidden, n_feature)
            self.dropout = nn.Dropout(dropout)
            self.norm = nn.LayerNorm(n_hidden)
            self.norm_layer = nn.LayerNorm(n_feature)
            self.alpha = nn.Parameter(torch.zeros(1))

        def forward(self, x: Any) -> Any:
            residual = x
            y = functional.relu(self.norm(self.linear1(x)))
            y = self.dropout(y)
            y = self.linear2(y)
            y = self.dropout(y)
            return self.norm_layer(residual + self.alpha * y)

    class EncoderF(nn.Module):
        def __init__(
            self, n_freq: int, n_group: int, n_head: int, n_layer: int, dropout: float
        ) -> None:
            super().__init__()
            self.d_model = n_freq // n_group
            self.n_freq = n_freq
            self.n_group = n_group
            self.pr = 0.01
            self.attn_layer = nn.ModuleList(
                [
                    nn.MultiheadAttention(self.d_model, n_head, batch_first=True)
                    for _ in range(n_layer)
                ]
            )
            self.ff_layer = nn.ModuleList(
                [FeedForward(self.d_model, dropout) for _ in range(n_layer)]
            )
            self.attn_alphas = nn.ParameterList(
                [nn.Parameter(torch.zeros(1)) for _ in range(n_layer)]
            )
            self.dropout = nn.Dropout(dropout)
            self.fc = nn.Linear(n_freq, n_freq)
            self.norm_layer = nn.LayerNorm(n_freq)

        def forward(self, x: Any) -> Any:
            batch, time, _ = x.shape
            x = x.reshape(batch * time, self.n_group, self.d_model)
            pe = positional_encoding(x.shape[0], x.shape[1], x.shape[2]).to(x.device)
            x = x + pe * self.pr
            for idx, (attention, feed_forward) in enumerate(
                zip(self.attn_layer, self.ff_layer, strict=True)
            ):
                residual = x
                out, _ = attention(x, x, x, need_weights=False)
                x = feed_forward(residual + self.attn_alphas[idx] * out)
            reshaped = self.dropout(x.reshape(batch, time, self.n_freq))
            return self.norm_layer(self.fc(reshaped))

    class EncoderT(nn.Module):
        def __init__(self, n_freq: int, n_head: int, n_layer: int, dropout: float) -> None:
            super().__init__()
            self.n_freq = n_freq
            self.pr = 0.02
            self.attn_layer = nn.ModuleList(
                [nn.MultiheadAttention(n_freq, n_head, batch_first=True) for _ in range(n_layer)]
            )
            self.ff_layer = nn.ModuleList([FeedForward(n_freq, dropout) for _ in range(n_layer)])
            self.attn_alphas = nn.ParameterList(
                [nn.Parameter(torch.zeros(1)) for _ in range(n_layer)]
            )
            self.dropout = nn.Dropout(dropout)
            self.fc = nn.Linear(n_freq, n_freq)
            self.norm_layer = nn.LayerNorm(n_freq)

        def forward(self, x: Any) -> Any:
            batch, time, feature = x.shape
            x = x + positional_encoding(batch, time, feature).to(x.device) * self.pr
            for idx, (attention, feed_forward) in enumerate(
                zip(self.attn_layer, self.ff_layer, strict=True)
            ):
                residual = x
                out, _ = attention(x, x, x, need_weights=False)
                x = feed_forward(residual + self.attn_alphas[idx] * out)
            return self.norm_layer(self.fc(self.dropout(x)))

    class Decoder(nn.Module):
        def __init__(self, d_model: int, n_head: int, n_layer: int, dropout: float) -> None:
            super().__init__()
            self.r1 = 1.0
            self.r2 = 1.0
            self.wr = 1.0
            self.pr = 0.01
            self.attn_layer1 = nn.ModuleList(
                [nn.MultiheadAttention(d_model, n_head, batch_first=True) for _ in range(n_layer)]
            )
            self.attn_layer2 = nn.ModuleList(
                [nn.MultiheadAttention(d_model, n_head, batch_first=True) for _ in range(n_layer)]
            )
            self.ff_layer = nn.ModuleList([FeedForward(d_model, dropout) for _ in range(n_layer)])
            self.attn1_alphas = nn.ParameterList(
                [nn.Parameter(torch.zeros(1)) for _ in range(n_layer)]
            )
            self.attn2_alphas = nn.ParameterList(
                [nn.Parameter(torch.zeros(1)) for _ in range(n_layer)]
            )
            self.dropout = nn.Dropout(dropout)
            self.fc = nn.Linear(d_model, d_model)
            self.norm_layer = nn.LayerNorm(d_model)

        def forward(self, x1: Any, x2: Any, weight: Any = None) -> Any:
            y = x1 * self.r1 + x2 * self.r2
            if weight is not None:
                while weight.dim() < y.dim():
                    weight = weight.unsqueeze(-1)
                if weight.shape[-1] == 1 and y.shape[-1] > 1:
                    weight = weight.expand_as(y)
                y = y + weight * self.wr
            pe = positional_encoding(y.shape[0], y.shape[1], y.shape[2]).to(y.device)
            y = y + pe * self.pr
            for idx in range(len(self.attn_layer1)):
                residual = y
                out1, _ = self.attn_layer1[idx](y, y, y, need_weights=False)
                y = self.norm_layer(residual + self.attn1_alphas[idx] * self.dropout(out1))
                residual = y
                out2, _ = self.attn_layer2[idx](y, x2, x2, need_weights=False)
                y = self.norm_layer(residual + self.attn2_alphas[idx] * self.dropout(out2))
                y = self.ff_layer[idx](y)
            return self.fc(self.dropout(y)), y

    class BaseTransformer(nn.Module):
        def __init__(self, params: dict[str, Any]) -> None:
            super().__init__()
            n_freq = int(params["n_freq"])
            self.encoder_f = nn.ModuleList(
                [
                    EncoderF(
                        n_freq,
                        int(params["n_group"]),
                        int(params["f_head"]),
                        int(params["f_layer"]),
                        float(params["dropout"]),
                    )
                ]
            )
            self.encoder_t = nn.ModuleList(
                [
                    EncoderT(
                        n_freq,
                        int(params["t_head"]),
                        int(params["t_layer"]),
                        float(params["dropout"]),
                    )
                ]
            )
            self.decoder = Decoder(
                n_freq,
                int(params["d_head"]),
                int(params["d_layer"]),
                float(params["dropout"]),
            )

        def forward(self, x: Any, weight: Any = None) -> Any:
            if x.ndim == 3:
                x = x.unsqueeze(1)
            encoded_f = self.encoder_f[0](x[:, 0, :, :])
            encoded_t = self.encoder_t[0](x[:, 0, :, :])
            return self.decoder(encoded_f, encoded_t, weight)

    def smooth_logits(logits: Any, kernel_size: int = SMOOTH_KERNEL_SIZE) -> Any:
        kernel_size = max(1, int(kernel_size))
        if kernel_size % 2 == 0:
            kernel_size += 1
        if logits.dim() == 3:
            transposed = logits.transpose(1, 2)
            smoothed = functional.avg_pool1d(
                transposed,
                kernel_size=kernel_size,
                stride=1,
                padding=kernel_size // 2,
            )
            return smoothed.transpose(1, 2)
        return logits

    class ChordNet(nn.Module):
        def __init__(self, params: dict[str, Any]) -> None:
            super().__init__()
            self.transformer = BaseTransformer(params)
            self.dropout = nn.Dropout(float(params["dropout"]))
            self.fc = nn.Linear(int(params["n_freq"]), int(params["n_classes"]))

        def forward(self, x: Any) -> tuple[Any, Any]:
            if x.dim() == 3:
                x = x.unsqueeze(1)
            _, features = self.transformer(x)
            features = self.dropout(features)
            return self.fc(features), features

        def predict(self, x: Any) -> Any:
            self.eval()
            with torch.no_grad():
                logits, _ = self.forward(x)
                return smooth_logits(logits).argmax(dim=-1)

    params = _architecture(state_dict, checkpoint)
    model = ChordNet(params)
    try:
        model.load_state_dict(state_dict)
    except RuntimeError as exc:
        raise RuntimeError(f"ChordMini checkpoint is incompatible with the pinned model: {exc}") from exc
    model.eval()
    return model


def _extract_features(audio_path: str | Path) -> tuple[Any, float, float]:
    import librosa
    import numpy as np

    audio, sample_rate = librosa.load(str(audio_path), sr=SAMPLE_RATE, mono=True)
    cqt = librosa.cqt(
        audio,
        sr=sample_rate,
        n_bins=N_BINS,
        bins_per_octave=BINS_PER_OCTAVE,
        hop_length=HOP_LENGTH,
        fmin=librosa.note_to_hz("C1"),
    )
    features = np.log(np.abs(cqt) + 1e-6).T.astype(np.float32)
    frame_duration = float(HOP_LENGTH) / float(sample_rate)
    song_duration = float(len(audio)) / float(sample_rate)
    return features, frame_duration, song_duration


def _predict_frames(model: Any, features: Any, mean: float, std: float) -> Any:
    import numpy as np
    import torch

    original_frames = int(features.shape[0])
    if original_frames == 0:
        return np.array([], dtype=np.int64)

    remainder = original_frames % SEQ_LEN
    num_pad = 0 if remainder == 0 else SEQ_LEN - remainder
    padded = np.pad(features, ((0, num_pad), (0, 0)), mode="constant")
    stride = max(1, int(SEQ_LEN * (1.0 - OVERLAP_RATIO)))
    padded_frames = int(padded.shape[0])
    starts = list(range(0, max(1, padded_frames - SEQ_LEN + 1), stride))
    final_start = max(0, padded_frames - SEQ_LEN)
    if final_start not in starts:
        starts.append(final_start)

    votes = np.zeros((original_frames, N_CLASSES), dtype=np.float32)
    counts = np.zeros(original_frames, dtype=np.int32)
    device = next(model.parameters()).device

    with torch.no_grad():
        for batch_start in range(0, len(starts), BATCH_SIZE):
            batch_meta: list[tuple[int, int]] = []
            batch_windows: list[Any] = []
            for start in starts[batch_start : batch_start + BATCH_SIZE]:
                valid_len = min(SEQ_LEN, max(0, original_frames - start))
                if valid_len <= 0:
                    continue
                batch_windows.append(padded[start : start + SEQ_LEN])
                batch_meta.append((start, valid_len))
            if not batch_windows:
                continue
            tensor = torch.from_numpy(np.stack(batch_windows)).float().to(device)
            tensor = (tensor - float(mean)) / (float(std) + 1e-8)
            predictions = model.predict(tensor).detach().cpu().numpy()
            for local_idx, (start, valid_len) in enumerate(batch_meta):
                for offset in range(valid_len):
                    votes[start + offset, int(predictions[local_idx, offset])] += 1.0
                    counts[start + offset] += 1

    result = np.full(original_frames, 169, dtype=np.int64)
    valid = counts > 0
    result[valid] = np.argmax(votes[valid], axis=1)
    return result


def _segments(predictions: Any, frame_duration: float, song_duration: float) -> list[tuple[float, float, str]]:
    if len(predictions) == 0:
        return []
    vocabulary = _idx_to_chord()
    segments: list[tuple[float, float, str]] = []
    previous = int(predictions[0])
    start = 0.0
    for frame_index in range(1, len(predictions)):
        current = int(predictions[frame_index])
        if current == previous:
            continue
        end = min(float(frame_index) * frame_duration, song_duration)
        if end > start:
            segments.append((start, end, vocabulary.get(previous, "N")))
        start = end
        previous = current
    final_end = min(float(len(predictions)) * frame_duration, song_duration)
    if final_end > start:
        segments.append((start, final_end, vocabulary.get(previous, "N")))
    return segments


def infer_chords(audio_path: str | Path, checkpoint_path: str | Path) -> ChordMiniInferenceResult:
    """Run pinned ChordMini 2E1D inference on one local audio file."""
    _, checkpoint_sha256 = validate_checkpoint(checkpoint_path)

    try:
        import torch
    except ImportError as exc:
        raise RuntimeError(
            "ChordMini requires the backend worker Torch runtime. "
            "Install the worker dependency group."
        ) from exc

    checkpoint = torch.load(checkpoint_path, map_location="cpu", weights_only=False)
    if not isinstance(checkpoint, dict):
        raise RuntimeError("ChordMini checkpoint payload is not a mapping")
    state_dict = _extract_state_dict(checkpoint)
    mean, std = _normalization_stats(checkpoint)
    model = _build_model(state_dict, checkpoint, torch)

    features, frame_duration, song_duration = _extract_features(audio_path)
    predictions = _predict_frames(model, features, mean, std)
    max_frames = int(song_duration // frame_duration) if frame_duration > 0 else len(predictions)
    if max_frames > 0:
        predictions = predictions[:max_frames]
    segments = _segments(predictions, frame_duration, song_duration)
    return ChordMiniInferenceResult(
        segments=segments,
        checkpoint_sha256=checkpoint_sha256,
        frame_duration=frame_duration,
        frame_count=int(len(predictions)),
    )
