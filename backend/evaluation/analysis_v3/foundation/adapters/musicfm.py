"""MusicFM adapter: official FMA checkpoint."""

from __future__ import annotations

import os
import sys

import numpy as np

from .base import EmbeddingResult, FoundationModelAdapter, ModelMetadata


class MusicFMAdapter(FoundationModelAdapter):
    name = "musicfm"
    model_id = "minzwon/MusicFM"

    def __init__(self, device: str = "cpu"):
        super().__init__(device)
        self._model = None
        self._musicfm_path = None

    def load(self) -> None:
        if self._loaded:
            return
        try:
            from huggingface_hub import hf_hub_download

            stat_path = hf_hub_download(self.model_id, "fma_stats.json")
            model_path = hf_hub_download(self.model_id, "pretrained_fma.pt")

            musicfm_dir = "/tmp/musicfm"
            if not os.path.exists(musicfm_dir):
                import subprocess

                subprocess.run(
                    ["git", "clone", "https://github.com/minzwon/musicfm.git", musicfm_dir],
                    check=True,
                    capture_output=True,
                )

            sys.path.insert(0, musicfm_dir)
            from model.musicfm_25hz import MusicFM25Hz

            self._model = MusicFM25Hz(
                is_flash=False,
                stat_path=stat_path,
                model_path=model_path,
            )
            self._model.eval()
            self._model.to(self.device)
            self._loaded = True
        except Exception as e:
            raise RuntimeError(f"Failed to load MusicFM: {e}") from e

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

            waveform_tensor = torch.from_numpy(waveform).float().unsqueeze(0).to(self.device)

            with torch.no_grad():
                emb = self._model.get_latent(waveform_tensor, layer_ix=7)

            if emb.dim() == 3:
                mean_pooled = emb.mean(dim=1).squeeze().cpu().numpy()
                temporal = emb.squeeze(0).cpu().numpy()
            else:
                mean_pooled = emb.squeeze().cpu().numpy()
                temporal = None

            return EmbeddingResult(
                vector=mean_pooled,
                temporal_vectors=temporal,
                temporal_resolution_seconds=0.04 if temporal is not None else None,
                dimensionality=mean_pooled.shape[0],
                normalized=False,
            )
        except Exception as e:
            return EmbeddingResult(error=str(e))

    def metadata(self) -> ModelMetadata:
        return ModelMetadata(
            candidate="musicfm",
            model_id=self.model_id,
            code_license="MIT",
            weight_license="CC-BY-NC-SA-4.0",
            training_data_notes="FMA dataset; weights are non-commercial per upstream.",
            embedding_dim=1024,
            temporal=True,
            temporal_resolution_seconds=0.04,
            supports_audio=True,
            supports_text=False,
            supports_symbolic=False,
            upstream_repo="https://github.com/minzwon/musicfm",
            notes="Self-supervised music foundation model trained on FMA. 25Hz frame rate.",
        )
