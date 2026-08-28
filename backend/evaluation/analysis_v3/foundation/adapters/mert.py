"""MERT adapter: m-a-p/MERT-v1-95M."""

from __future__ import annotations

import numpy as np

from .base import EmbeddingResult, FoundationModelAdapter, ModelMetadata


class MERTAdapter(FoundationModelAdapter):
    name = "mert"
    model_id = "m-a-p/MERT-v1-95M"

    def __init__(self, device: str = "cpu"):
        super().__init__(device)
        self._model = None
        self._processor = None

    def load(self) -> None:
        if self._loaded:
            return
        try:
            from transformers import AutoFeatureExtractor, AutoModel

            self._processor = AutoFeatureExtractor.from_pretrained(
                self.model_id, trust_remote_code=True
            )
            self._model = AutoModel.from_pretrained(self.model_id, trust_remote_code=True)
            self._model.eval()
            self._model.to(self.device)
            self._loaded = True
        except Exception as e:
            raise RuntimeError(f"Failed to load MERT: {e}") from e

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
                resampler = torchaudio.transforms.Resample(orig_freq=sample_rate, new_freq=24000)
                waveform = resampler(waveform).squeeze(0).numpy()
            else:
                waveform = audio

            inputs = self._processor(
                waveform,
                sampling_rate=24000,
                return_tensors="pt",
                padding=True,
            )
            inputs = {k: v.to(self.device) for k, v in inputs.items()}

            with torch.no_grad():
                outputs = self._model(**inputs)

            hidden_states = outputs.last_hidden_state
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
            candidate="mert",
            model_id=self.model_id,
            code_license="MIT",
            weight_license="CC-BY-NC-SA-4.0",
            training_data_notes="MERT training data includes copyrighted music.",
            embedding_dim=768,
            temporal=True,
            temporal_resolution_seconds=0.02,
            supports_audio=True,
            supports_text=False,
            supports_symbolic=False,
            upstream_repo="https://github.com/yizhilll/MERT",
            notes="95M parameter music understanding model.",
        )
