"""Experimental source-separation interface (Demucs/HTDemucs).

Not part of production. Used only by the evaluation benchmark.

Engine facts (verified at integration time):
  - library: demucs 4.0.1 — official continuation of facebookresearch/demucs by
    the original author (adefossez/demucs); author notes it is not actively
    developed, so expect slow replies / no new features
  - model:   htdemucs (hybrid transformer)
  - license: MIT (library + model)
  - sources: drums, bass, other, vocals
  - model download: ~80 MB
  - input:    stereo 44.1 kHz (mono is upmixed; sample rate is resampled)
  - device:   CPU or GPU (CPU verified here)
"""

from __future__ import annotations

import numpy as np

DEMUCS_SOURCES = ("drums", "bass", "other", "vocals")

# Sources that are pitched-note transcription targets (drums excluded).
PITCHED_SOURCES = ("bass", "other", "vocals")


def _to_model_input(audio: np.ndarray, samplerate: int, model) -> np.ndarray:
    """Resample to the model sample rate and upmix mono to stereo."""
    import torch
    from demucs.audio import convert_audio

    wav = np.asarray(audio, dtype=np.float32)
    if wav.ndim == 1:
        wav = wav[None, :]
    tensor = torch.from_numpy(wav)
    tensor = convert_audio(tensor, samplerate, model.samplerate, model.audio_channels)
    # convert_audio returns [channels, samples]; ensure stereo.
    if tensor.shape[0] == 1:
        tensor = tensor.repeat(2, 1)
    return tensor.numpy()


def separate(
    audio: np.ndarray,
    samplerate: int,
    model_name: str = "htdemucs",
    device: str | None = None,
) -> dict[str, np.ndarray]:
    """Separate a mono/stereo audio array into named stems.

    Returns a dict mapping each source name to a 1-D float32 numpy array at the
    model's sample rate (44.1 kHz).
    """
    import torch
    from demucs.apply import apply_model
    from demucs.pretrained import get_model

    model = get_model(model_name)
    if device is None:
        device = "cuda" if torch.cuda.is_available() else "cpu"

    wav = _to_model_input(audio, samplerate, model)
    tensor = torch.from_numpy(wav)
    ref = tensor.mean(0)
    tensor = (tensor - ref.mean()) / (ref.std() + 1e-8)

    sources = apply_model(model, tensor[None], device=device, progress=True)
    sources = sources[0] * (ref.std() + 1e-8) + ref.mean()

    out: dict[str, np.ndarray] = {}
    for idx, name in enumerate(DEMUCS_SOURCES):
        stem = sources[idx].mean(0)
        out[name] = stem.numpy().astype(np.float32)
    return out
