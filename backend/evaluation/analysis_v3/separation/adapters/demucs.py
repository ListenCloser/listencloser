"""Demucs adapter."""

from __future__ import annotations

import numpy as np

from .base import SeparationAdapter, SeparationMetadata, SeparationResult


class DemucsAdapter(SeparationAdapter):
    name = "demucs"
    model_id = "facebookresearch/demucs"

    def __init__(self, device: str = "cpu"):
        super().__init__(device)
        self._model = None

    def load(self) -> None:
        if self._loaded:
            return
        try:
            from demucs.pretrained import get_model

            self._model = get_model("htdemucs")
            self._model.eval()
            self._model.to(self.device)
            self._loaded = True
        except Exception as e:
            raise RuntimeError(f"Failed to load Demucs: {e}") from e

    def separate(
        self,
        audio: np.ndarray,
        sample_rate: int,
    ) -> SeparationResult:
        if not self._loaded:
            return SeparationResult(error="Model not loaded")
        try:
            import torch
            from demucs.apply import apply_model

            if audio.ndim == 1:
                audio = np.stack([audio, audio], axis=0)
            elif audio.ndim == 2 and audio.shape[0] == 1:
                audio = np.concatenate([audio, audio], axis=0)

            waveform = torch.from_numpy(audio).float().unsqueeze(0).to(self.device)

            with torch.no_grad():
                sources = apply_model(self._model, waveform, device=self.device)

            if sources.dim() == 4:
                sources = sources.squeeze(0)

            stem_names = (
                self._model.sources
                if hasattr(self._model, "sources")
                else ["drums", "bass", "other", "vocals"]
            )

            result = SeparationResult()
            for i, name in enumerate(stem_names):
                if i < sources.shape[0]:
                    stem_audio = sources[i].cpu().numpy()
                    if name == "vocals":
                        result.vocals = stem_audio
                    elif name == "drums":
                        result.drums = stem_audio
                    elif name == "bass":
                        result.bass = stem_audio
                    elif name == "other":
                        result.other = stem_audio

            return result
        except Exception as e:
            return SeparationResult(error=str(e))

    def metadata(self) -> SeparationMetadata:
        return SeparationMetadata(
            candidate="demucs",
            model_id=self.model_id,
            code_license="MIT",
            weight_license="MIT",
            upstream_repo="https://github.com/facebookresearch/demucs",
            supports_vocals=True,
            supports_drums=True,
            supports_bass=True,
            supports_other=True,
            num_stems=4,
            notes="Hybrid Transformer Demucs. MIT licensed.",
        )
