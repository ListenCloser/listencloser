"""MuQ adapter: OpenMuQ/MuQ-large-msd-iter."""

from __future__ import annotations

import numpy as np

from .base import EmbeddingResult, FoundationModelAdapter, ModelMetadata


class MuQAdapter(FoundationModelAdapter):
    name = "muq"
    model_id = "OpenMuQ/MuQ-large-msd-iter"

    def __init__(self, device: str = "cpu"):
        super().__init__(device)
        self._model = None

    def load(self) -> None:
        if self._loaded:
            return
        try:
            from muq import MuQ

            self._model = MuQ.from_pretrained(self.model_id)
            self._model.eval()
            self._model.to(self.device)
            self._loaded = True
        except Exception as e:
            raise RuntimeError(f"Failed to load MuQ: {e}") from e

    def embed_audio(
        self,
        audio: np.ndarray,
        sample_rate: int,
    ) -> EmbeddingResult:
        if not self._loaded:
            return EmbeddingResult(error="Model not loaded")
        try:
            import torch

            if sample_rate != 24000:
                import torchaudio

                waveform = torch.from_numpy(audio).float().unsqueeze(0)
                if waveform.dim() == 1:
                    waveform = waveform.unsqueeze(0)
                resampler = torchaudio.transforms.Resample(
                    orig_freq=sample_rate, new_freq=24000
                )
                waveform = resampler(waveform).squeeze(0).numpy()
            else:
                waveform = audio

            waveform_tensor = torch.from_numpy(waveform).float().unsqueeze(0).to(self.device)

            with torch.no_grad():
                outputs = self._model(waveform_tensor)

            if isinstance(outputs, torch.Tensor):
                hidden_states = outputs
            elif hasattr(outputs, "last_hidden_state"):
                hidden_states = outputs.last_hidden_state
            else:
                hidden_states = outputs[0] if isinstance(outputs, (tuple, list)) else outputs

            mean_pooled = hidden_states.mean(dim=1).squeeze().cpu().numpy()

            return EmbeddingResult(
                vector=mean_pooled,
                temporal_vectors=hidden_states.squeeze(0).cpu().numpy(),
                temporal_resolution_seconds=0.02,
                dimensionality=mean_pooled.shape[0],
                normalized=False,
            )
        except Exception as e:
            return EmbeddingResult(error=str(e))

    def metadata(self) -> ModelMetadata:
        return ModelMetadata(
            candidate="muq",
            model_id=self.model_id,
            code_license="MIT",
            weight_license="CC-BY-NC-4.0",
            training_data_notes="MSD training data; weights are non-commercial per upstream.",
            embedding_dim=1024,
            temporal=True,
            temporal_resolution_seconds=0.02,
            supports_audio=True,
            supports_text=False,
            supports_symbolic=False,
            upstream_repo="https://github.com/tencent-ailab/MuQ",
            notes="Large music quality model trained on MSD with iterative refinement.",
        )
