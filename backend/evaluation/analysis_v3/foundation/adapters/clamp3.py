"""CLaMP3 adapter: official implementation from sander-wood/clamp3."""

from __future__ import annotations

import os
import sys
import tempfile

import numpy as np

from .base import EmbeddingResult, FoundationModelAdapter, ModelMetadata


class CLaMP3Adapter(FoundationModelAdapter):
    name = "clamp3"
    model_id = "sander-wood/clamp3"

    def __init__(self, device: str = "cpu"):
        super().__init__(device)
        self._model = None
        self._tokenizer = None
        self._patchilizer = None
        self._clamp3_path = None

    def load(self) -> None:
        if self._loaded:
            return
        try:
            import torch
            from huggingface_hub import hf_hub_download
            from transformers import AutoTokenizer

            weights_path = hf_hub_download(
                self.model_id,
                "weights_clamp3_saas_h_size_768_t_model_FacebookAI_xlm-roberta-base_t_length_128_a_size_768_a_layers_12_a_length_128_s_size_768_s_layers_12_p_size_64_p_length_512.pth"
            )

            clamp3_dir = "/tmp/clamp3"
            if not os.path.exists(clamp3_dir):
                import subprocess
                subprocess.run(
                    ["git", "clone", "https://github.com/sanderwood/clamp3.git", clamp3_dir],
                    check=True,
                    capture_output=True,
                )

            sys.path.insert(0, os.path.join(clamp3_dir, "code"))

            from config import (
                AUDIO_HIDDEN_SIZE,
                AUDIO_NUM_LAYERS,
                CLAMP3_HIDDEN_SIZE,
                CLAMP3_LOAD_M3,
                MAX_AUDIO_LENGTH,
                MAX_TEXT_LENGTH,
                M3_HIDDEN_SIZE,
                PATCH_LENGTH,
                PATCH_NUM_LAYERS,
                PATCH_SIZE,
                TEXT_MODEL_NAME,
            )
            from utils import CLaMP3Model, M3Patchilizer

            from transformers import BertConfig

            audio_config = BertConfig(
                vocab_size=1,
                hidden_size=AUDIO_HIDDEN_SIZE,
                num_hidden_layers=AUDIO_NUM_LAYERS,
                num_attention_heads=AUDIO_HIDDEN_SIZE // 64,
                intermediate_size=AUDIO_HIDDEN_SIZE * 4,
                max_position_embeddings=MAX_AUDIO_LENGTH,
            )
            symbolic_config = BertConfig(
                vocab_size=1,
                hidden_size=M3_HIDDEN_SIZE,
                num_hidden_layers=PATCH_NUM_LAYERS,
                num_attention_heads=M3_HIDDEN_SIZE // 64,
                intermediate_size=M3_HIDDEN_SIZE * 4,
                max_position_embeddings=PATCH_LENGTH,
            )

            self._model = CLaMP3Model(
                audio_config=audio_config,
                symbolic_config=symbolic_config,
                text_model_name=TEXT_MODEL_NAME,
                hidden_size=CLAMP3_HIDDEN_SIZE,
                load_m3=CLAMP3_LOAD_M3,
            )

            checkpoint = torch.load(weights_path, map_location="cpu", weights_only=True)
            self._model.load_state_dict(checkpoint["model"])
            self._model.eval()
            self._model.to(self.device)

            self._tokenizer = AutoTokenizer.from_pretrained(TEXT_MODEL_NAME)
            self._patchilizer = M3Patchilizer()

            self._loaded = True
        except Exception as e:
            raise RuntimeError(f"Failed to load CLaMP3: {e}") from e

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

            mert_adapter = _MERTFeatureExtractor(device=self.device)
            features = mert_adapter.extract(waveform, sample_rate=24000)

            features_tensor = torch.from_numpy(features).float().to(self.device)

            from config import MAX_AUDIO_LENGTH

            segment_list = []
            for i in range(0, len(features_tensor), MAX_AUDIO_LENGTH):
                segment_list.append(features_tensor[i:i + MAX_AUDIO_LENGTH])
            if len(segment_list) > 0:
                segment_list[-1] = features_tensor[-MAX_AUDIO_LENGTH:]

            embeddings = []
            for segment in segment_list:
                input_masks = torch.tensor([1.0] * segment.size(0))
                pad_len = MAX_AUDIO_LENGTH - segment.size(0)
                if pad_len > 0:
                    pad = torch.zeros(pad_len, segment.size(1)).to(self.device)
                    segment = torch.cat([segment, pad], 0)
                    input_masks = torch.cat([input_masks, torch.zeros(pad_len)], 0)

                with torch.no_grad():
                    emb = self._model.get_audio_features(
                        audio_inputs=segment.unsqueeze(0).to(self.device),
                        audio_masks=input_masks.unsqueeze(0).to(self.device),
                        get_global=True,
                    )
                embeddings.append(emb)

            if embeddings:
                mean_emb = torch.stack(embeddings).mean(dim=0).squeeze().cpu().numpy()
            else:
                return EmbeddingResult(error="No embeddings generated")

            return EmbeddingResult(
                vector=mean_emb,
                dimensionality=mean_emb.shape[0],
                normalized=True,
            )
        except Exception as e:
            return EmbeddingResult(error=str(e))

    def embed_text(self, text: str) -> EmbeddingResult | None:
        if not self._loaded:
            return None
        try:
            import torch

            from config import MAX_TEXT_LENGTH

            input_data = self._tokenizer(text, return_tensors="pt")["input_ids"].squeeze(0)

            segment_list = []
            for i in range(0, len(input_data), MAX_TEXT_LENGTH):
                segment_list.append(input_data[i:i + MAX_TEXT_LENGTH])
            if len(segment_list) > 0:
                segment_list[-1] = input_data[-MAX_TEXT_LENGTH:]

            embeddings = []
            for segment in segment_list:
                input_masks = torch.tensor([1.0] * segment.size(0))
                pad_len = MAX_TEXT_LENGTH - segment.size(0)
                if pad_len > 0:
                    pad = torch.ones(pad_len).long() * self._tokenizer.pad_token_id
                    segment = torch.cat([segment, pad], 0)
                    input_masks = torch.cat([input_masks, torch.zeros(pad_len)], 0)

                with torch.no_grad():
                    emb = self._model.get_text_features(
                        text_inputs=segment.unsqueeze(0).to(self.device),
                        text_masks=input_masks.unsqueeze(0).to(self.device),
                        get_global=True,
                    )
                embeddings.append(emb)

            if embeddings:
                mean_emb = torch.stack(embeddings).mean(dim=0).squeeze().cpu().numpy()
            else:
                return None

            return EmbeddingResult(
                vector=mean_emb,
                dimensionality=mean_emb.shape[0],
                normalized=True,
            )
        except Exception as e:
            return EmbeddingResult(error=str(e))

    def supports_text(self) -> bool:
        return True

    def supports_symbolic(self) -> bool:
        return True

    def embed_symbolic(self, midi_bytes: bytes) -> EmbeddingResult | None:
        if not self._loaded:
            return None
        try:
            import torch
            import subprocess

            from config import PATCH_LENGTH, PATCH_SIZE

            with tempfile.NamedTemporaryFile(suffix=".mid", delete=False) as f:
                f.write(midi_bytes)
                midi_path = f.name

            try:
                clamp3_dir = "/tmp/clamp3"
                mtf_dir = tempfile.mkdtemp()
                subprocess.run(
                    ["python3", os.path.join(clamp3_dir, "preprocessing", "midi", "batch_midi2mtf.py"),
                     os.path.dirname(midi_path), mtf_dir, "--m3_compatible"],
                    check=True,
                    capture_output=True,
                )

                mtf_files = [f for f in os.listdir(mtf_dir) if f.endswith(".mtf")]
                if not mtf_files:
                    return EmbeddingResult(error="Failed to convert MIDI to MTF")

                with open(os.path.join(mtf_dir, mtf_files[0]), "r") as f:
                    mtf_content = f.read()

                input_data = self._patchilizer.encode(mtf_content, add_special_patches=True)
                input_data = torch.tensor(input_data)

                segment_list = []
                for i in range(0, len(input_data), PATCH_LENGTH):
                    segment_list.append(input_data[i:i + PATCH_LENGTH])
                if len(segment_list) > 0:
                    segment_list[-1] = input_data[-PATCH_LENGTH:]

                embeddings = []
                for segment in segment_list:
                    input_masks = torch.tensor([1.0] * segment.size(0))
                    pad_len = PATCH_LENGTH - segment.size(0)
                    if pad_len > 0:
                        pad = torch.ones(pad_len, PATCH_SIZE).long() * self._patchilizer.pad_token_id
                        segment = torch.cat([segment, pad], 0)
                        input_masks = torch.cat([input_masks, torch.zeros(pad_len)], 0)

                    with torch.no_grad():
                        emb = self._model.get_symbolic_features(
                            symbolic_inputs=segment.unsqueeze(0).to(self.device),
                            symbolic_masks=input_masks.unsqueeze(0).to(self.device),
                            get_global=True,
                        )
                    embeddings.append(emb)

                if embeddings:
                    mean_emb = torch.stack(embeddings).mean(dim=0).squeeze().cpu().numpy()
                else:
                    return EmbeddingResult(error="No embeddings generated")

                return EmbeddingResult(
                    vector=mean_emb,
                    dimensionality=mean_emb.shape[0],
                    normalized=True,
                )
            finally:
                os.unlink(midi_path)
        except Exception as e:
            return EmbeddingResult(error=str(e))

    def metadata(self) -> ModelMetadata:
        return ModelMetadata(
            candidate="clamp3",
            model_id=self.model_id,
            code_license="MIT",
            weight_license="MIT",
            training_data_notes="CLaMP3 training data includes audio, MIDI, and MusicXML. Uses MERT for audio feature extraction.",
            embedding_dim=768,
            temporal=False,
            supports_audio=True,
            supports_text=True,
            supports_symbolic=True,
            upstream_repo="https://github.com/sanderwood/clamp3",
            notes="Cross-modal music model supporting audio, text, and symbolic. Requires MERT for audio features.",
        )


class _MERTFeatureExtractor:
    def __init__(self, device: str = "cpu"):
        self.device = device
        self._model = None
        self._processor = None

    def _load(self):
        if self._model is not None:
            return
        from transformers import AutoModel, AutoFeatureExtractor

        self._processor = AutoFeatureExtractor.from_pretrained(
            "m-a-p/MERT-v1-95M", trust_remote_code=True
        )
        self._model = AutoModel.from_pretrained(
            "m-a-p/MERT-v1-95M", trust_remote_code=True
        )
        self._model.eval()
        self._model.to(self.device)

    def extract(self, audio: np.ndarray, sample_rate: int = 24000) -> np.ndarray:
        self._load()
        import torch

        inputs = self._processor(
            audio,
            sampling_rate=sample_rate,
            return_tensors="pt",
            padding=True,
        )
        inputs = {k: v.to(self.device) for k, v in inputs.items()}

        with torch.no_grad():
            outputs = self._model(**inputs)

        return outputs.last_hidden_state.squeeze(0).cpu().numpy()
