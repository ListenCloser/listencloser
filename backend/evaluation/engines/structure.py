"""Structure engine adapters for OSS evaluation.

Adapters for:
- All-In-One (existing baseline)
- all-in-one-infer variant (if maintained)
"""

from __future__ import annotations

import logging
import os
import tempfile
from contextlib import suppress
from dataclasses import dataclass
from typing import Any

from evaluation.engines import EngineAdapter, EngineInfo

logger = logging.getLogger("eval.engines.structure")


# ============================================================
# All-In-One (existing baseline - already in production)
# ============================================================


@dataclass
class AllInOneAdapter(EngineAdapter):
    engine_info = EngineInfo(
        name="all_in_one",
        category="structure",
        repo_url="https://github.com/all-in-one/audio_structure",
        license="MIT",
        install_cmd="pip install allin1",
        model_size_mb=100,
        requires_gpu=True,
        notes="Joint beat/downbeat/segmentation model. Current production baseline (optional).",
    )

    def __init__(self, device: str = "cpu", **kwargs):
        self._device = device
        self._model = None

    def is_available(self) -> bool:
        try:
            import allin1  # noqa: F401
            import torch  # noqa: F401

            return True
        except Exception:
            return False

    def prepare(self) -> None:
        if self._model is not None:
            return
        try:
            from allin1 import AllInOne

            self._model = AllInOne(device=self._device)
        except Exception as e:
            logger.warning("AllInOne prepare failed: %s", e)
            self._model = None

    def analyze_structure(self, audio_bytes: bytes, **kwargs) -> dict[str, Any]:
        if self._model is None:
            self.prepare()
        if self._model is None:
            raise RuntimeError("AllInOne model not available")

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            f.write(audio_bytes)
            temp_path = f.name

        try:
            result = self._model.predict(temp_path)
            return {
                "bpm": result.get("bpm"),
                "beats": result.get("beats"),
                "downbeats": result.get("downbeats"),
                "segments": result.get("segments", []),
            }
        finally:
            with suppress(Exception):
                os.unlink(temp_path)

    def transcribe(self, audio_bytes: bytes, **kwargs) -> dict[str, Any]:
        raise NotImplementedError

    def estimate_beats(self, audio_bytes: bytes, **kwargs) -> dict[str, Any]:
        raise NotImplementedError

    def analyze_harmony(self, midi_bytes: bytes, **kwargs) -> dict[str, Any]:
        raise NotImplementedError


# ============================================================
# Registry
# ============================================================

STRUCTURE_ADAPTERS = {
    "all_in_one": AllInOneAdapter,
    # "all_in_one_infer": AllInOneInferAdapter,  # If maintained variant exists
}


def get_structure_adapter(name: str, **kwargs) -> EngineAdapter:
    if name not in STRUCTURE_ADAPTERS:
        raise ValueError(
            f"Unknown structure adapter: {name}. Available: {list(STRUCTURE_ADAPTERS)}"
        )
    return STRUCTURE_ADAPTERS[name](**kwargs)


def list_structure_adapters() -> list[str]:
    return list(STRUCTURE_ADAPTERS.keys())
