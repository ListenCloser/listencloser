"""CLAP adapter: LAION CLAP music-specific checkpoint."""

from __future__ import annotations

import numpy as np

from .base import EmbeddingResult, FoundationModelAdapter, ModelMetadata


class CLAPAdapter(FoundationModelAdapter):
    name = "clap"
    model_id = "laion/larger_clap_music"

    def __init__(self, device: str = "cpu"):
        super().__init__(device)
        self._model = None
        self._processor = None

    def load(self) -> None:
        if self._loaded:
            return
        try:
            from transformers import AutoModel, AutoProcessor

            self._processor = AutoProcessor.from_pretrained(self.model_id, trust_remote_code=True)
            self._model = AutoModel.from_pretrained(self.model_id, trust_remote_code=True)
            self._model.eval()
            self._model.to(self.device)
            self._loaded = True
        except Exception as e:
            raise RuntimeError(f"Failed to load CLAP: {e}") from e

    def embed_audio(
        self,
        audio: np.ndarray,
        sample_rate: int,
    ) -> EmbeddingResult:
        if not self._loaded:
            return EmbeddingResult(error="Model not loaded")
        try:
            import torch

            if sample_rate != 48000:
                import torchaudio

                waveform = torch.from_numpy(audio).float().unsqueeze(0)
                if waveform.dim() == 1:
                    waveform = waveform.unsqueeze(0)
                resampler = torchaudio.transforms.Resample(orig_freq=sample_rate, new_freq=48000)
                waveform = resampler(waveform).squeeze(0).numpy()
            else:
                waveform = audio

            inputs = self._processor(
                audios=waveform,
                sampling_rate=48000,
                return_tensors="pt",
                padding=True,
            )
            inputs = {k: v.to(self.device) for k, v in inputs.items()}

            with torch.no_grad():
                outputs = self._model.get_audio_features(**inputs)

            embedding = outputs.cpu().numpy().squeeze()

            return EmbeddingResult(
                vector=embedding,
                dimensionality=embedding.shape[0],
                normalized=True,
            )
        except Exception as e:
            return EmbeddingResult(error=str(e))

    def embed_text(self, text: str) -> EmbeddingResult | None:
        if not self._loaded:
            return None
        try:
            import torch

            inputs = self._processor(
                text=[text],
                return_tensors="pt",
                padding=True,
            )
            inputs = {k: v.to(self.device) for k, v in inputs.items()}

            with torch.no_grad():
                outputs = self._model.get_text_features(**inputs)

            embedding = outputs.cpu().numpy().squeeze()

            return EmbeddingResult(
                vector=embedding,
                dimensionality=embedding.shape[0],
                normalized=True,
            )
        except Exception as e:
            return EmbeddingResult(error=str(e))

    def supports_text(self) -> bool:
        return True

    def metadata(self) -> ModelMetadata:
        return ModelMetadata(
            candidate="clap",
            model_id=self.model_id,
            code_license="MIT",
            weight_license="MIT",
            training_data_notes="LAION AudioSet music subset.",
            embedding_dim=512,
            temporal=False,
            supports_audio=True,
            supports_text=True,
            supports_symbolic=False,
            upstream_repo="https://github.com/LAION-AI/CLAP",
            notes="Audio-text contrastive model. Music-specific checkpoint.",
        )
