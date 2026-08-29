"""Pinned HTDemucs adapter for the Analysis V3 separation benchmark."""

from __future__ import annotations

import hashlib
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

import numpy as np

from .base import SeparationAdapter, SeparationMetadata, SeparationResult

HTDEMUCS_PACKAGE_VERSION = "4.1.0"
HTDEMUCS_CHECKPOINT_ID = "955717e8"
HTDEMUCS_CHECKPOINT_FILE = "955717e8-8726e21a.th"
HTDEMUCS_CHECKPOINT_SHA256_PREFIX = "8726e21a"
HTDEMUCS_CODE_LICENSE_SOURCE = "https://pypi.org/project/demucs/4.1.0/"
HTDEMUCS_WEIGHT_LICENSE_SOURCE = "https://huggingface.co/adefossez/HTDemucs"


def _require_expected_package_version(installed_version: str) -> None:
    if installed_version != HTDEMUCS_PACKAGE_VERSION:
        raise RuntimeError(
            "Stage 2 requires exactly "
            f"demucs=={HTDEMUCS_PACKAGE_VERSION}; found demucs=={installed_version}"
        )


class DemucsAdapter(SeparationAdapter):
    name = "demucs"
    model_id = "demucs:htdemucs@955717e8"

    def __init__(self, device: str = "cpu"):
        super().__init__(device)
        self._model = None
        self._checkpoint_sha256: str | None = None
        self._checkpoint_size_mb: float | None = None
        self._upstream_version: str | None = None

    def _checkpoint_path(self) -> Path:
        import torch

        return Path(torch.hub.get_dir()) / "checkpoints" / HTDEMUCS_CHECKPOINT_FILE

    def load(self) -> None:
        if self._loaded:
            return
        try:
            try:
                self._upstream_version = version("demucs")
            except PackageNotFoundError as exc:
                raise RuntimeError(
                    f"demucs=={HTDEMUCS_PACKAGE_VERSION} is not installed"
                ) from exc
            _require_expected_package_version(self._upstream_version)

            from demucs.pretrained import get_model

            self._model = get_model("htdemucs")
            checkpoint_path = self._checkpoint_path()
            if not checkpoint_path.is_file():
                raise RuntimeError(
                    "htdemucs loaded without the expected official checkpoint artifact "
                    f"{HTDEMUCS_CHECKPOINT_FILE}; refusing an unpinned benchmark"
                )

            digest = hashlib.sha256()
            with checkpoint_path.open("rb") as handle:
                for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                    digest.update(chunk)
            self._checkpoint_sha256 = digest.hexdigest()
            if not self._checkpoint_sha256.startswith(HTDEMUCS_CHECKPOINT_SHA256_PREFIX):
                raise RuntimeError(
                    "htdemucs checkpoint checksum does not match the official filename prefix: "
                    f"{self._checkpoint_sha256}"
                )
            self._checkpoint_size_mb = round(checkpoint_path.stat().st_size / (1024 * 1024), 2)

            self._model.eval()
            self._model.to(self.device)
            self._loaded = True
        except Exception as error:
            raise RuntimeError(f"Failed to load pinned HTDemucs: {error}") from error

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
                # Disable random time-shift ensembling for the scientific bakeoff.
                # Stage 1 observed nondeterminism with the package default; a
                # deterministic candidate is required for per-piece deltas.
                sources = apply_model(
                    self._model,
                    waveform,
                    device=self.device,
                    shifts=0,
                )

            if sources.dim() == 4:
                sources = sources.squeeze(0)

            stem_names = (
                self._model.sources
                if hasattr(self._model, "sources")
                else ["drums", "bass", "other", "vocals"]
            )

            result = SeparationResult(
                metadata={
                    "package_version": self._upstream_version,
                    "checkpoint_id": HTDEMUCS_CHECKPOINT_ID,
                    "checkpoint_sha256": self._checkpoint_sha256,
                    "shifts": 0,
                }
            )
            for index, name in enumerate(stem_names):
                if index < sources.shape[0]:
                    stem_audio = sources[index].cpu().numpy()
                    if name == "vocals":
                        result.vocals = stem_audio
                    elif name == "drums":
                        result.drums = stem_audio
                    elif name == "bass":
                        result.bass = stem_audio
                    elif name == "other":
                        result.other = stem_audio

            return result
        except Exception as error:
            return SeparationResult(error=str(error))

    def metadata(self) -> SeparationMetadata:
        return SeparationMetadata(
            candidate="demucs",
            model_id=self.model_id,
            code_license="MIT",
            code_license_source=HTDEMUCS_CODE_LICENSE_SOURCE,
            weight_license="MIT",
            weight_license_source=HTDEMUCS_WEIGHT_LICENSE_SOURCE,
            upstream_repo="https://github.com/facebookresearch/demucs",
            upstream_version=self._upstream_version,
            checkpoint_id=HTDEMUCS_CHECKPOINT_ID,
            checkpoint_file=HTDEMUCS_CHECKPOINT_FILE,
            checkpoint_sha256=self._checkpoint_sha256,
            checkpoint_sha256_prefix=HTDEMUCS_CHECKPOINT_SHA256_PREFIX,
            checkpoint_size_mb=self._checkpoint_size_mb,
            supports_vocals=True,
            supports_drums=True,
            supports_bass=True,
            supports_other=True,
            num_stems=4,
            notes=(
                "Pinned Demucs 4.1.0 HTDemucs, official signature 955717e8. "
                "Evaluation uses shifts=0 for deterministic per-piece comparisons."
            ),
        )
