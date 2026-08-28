"""BS-RoFormer adapter."""

from __future__ import annotations

import numpy as np

from .base import SeparationAdapter, SeparationMetadata, SeparationResult


class BSRoFormerAdapter(SeparationAdapter):
    name = "bs_roformer"
    model_id = "lucidrains/BS-RoFormer"

    def __init__(self, device: str = "cpu"):
        super().__init__(device)
        self._model = None

    def load(self) -> None:
        if self._loaded:
            return
        try:
            from bs_roformer import BSRoformer

            self._model = BSRoformer(
                dim=384,
                depth=12,
                stereo=True,
                num_stems=4,
                time_steps=801,
                freq_bins=256,
            )
            self._model.eval()
            self._model.to(self.device)
            self._loaded = True
        except Exception as e:
            raise RuntimeError(f"Failed to load BS-RoFormer: {e}") from e

    def separate(
        self,
        audio: np.ndarray,
        sample_rate: int,
    ) -> SeparationResult:
        if not self._loaded:
            return SeparationResult(error="Model not loaded")
        try:
            import torch

            if audio.ndim == 1:
                audio = np.stack([audio, audio], axis=0)
            elif audio.ndim == 2 and audio.shape[0] == 1:
                audio = np.concatenate([audio, audio], axis=0)

            waveform = torch.from_numpy(audio).float().unsqueeze(0).to(self.device)

            with torch.no_grad():
                stems = self._model(waveform)

            if isinstance(stems, list | tuple):
                vocals = stems[0].squeeze().cpu().numpy() if len(stems) > 0 else None
                drums = stems[1].squeeze().cpu().numpy() if len(stems) > 1 else None
                bass = stems[2].squeeze().cpu().numpy() if len(stems) > 2 else None
                other = stems[3].squeeze().cpu().numpy() if len(stems) > 3 else None
            else:
                vocals = stems.squeeze().cpu().numpy()
                drums = None
                bass = None
                other = None

            return SeparationResult(
                vocals=vocals,
                drums=drums,
                bass=bass,
                other=other,
            )
        except Exception as e:
            return SeparationResult(error=str(e))

    def metadata(self) -> SeparationMetadata:
        return SeparationMetadata(
            candidate="bs_roformer",
            model_id=self.model_id,
            code_license="MIT",
            weight_license="CC-BY-NC-SA-4.0",
            upstream_repo="https://github.com/lucidrains/BS-RoFormer",
            supports_vocals=True,
            supports_drums=True,
            supports_bass=True,
            supports_other=True,
            num_stems=4,
            notes="Transformer-based source separation. Weight license requires verification.",
        )
