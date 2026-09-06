"""Optional SongFormer adapter for Structure V1 evaluation."""

from __future__ import annotations

import os
import sys
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any

from .base import StructureAdapter, StructureMetadata, StructureResult

_SONGFORMER_RELEASED_TRAINING_FAMILIES = (
    "HarmonixSet,SongFormDB-HX,SongFormDB-Ext,SongFormDB-Hook,SongFormDB-Gem"
)


def _csv_env(name: str, default: str = "") -> tuple[str, ...]:
    return tuple(
        value.strip() for value in os.environ.get(name, default).split(",") if value.strip()
    )


def _segments(raw: Any) -> list[dict[str, Any]]:
    if isinstance(raw, dict):
        raw = raw.get("segments", raw.get("result", []))
    result: list[dict[str, Any]] = []
    for segment in raw or []:
        if not isinstance(segment, dict):
            continue
        start = segment.get("start")
        end = segment.get("end")
        if start is None or end is None:
            continue
        start_s = float(start)
        end_s = float(end)
        if start_s < 0 or end_s <= start_s:
            continue
        result.append(
            {
                "start": start_s,
                "end": end_s,
                "label": str(segment.get("label", "")).strip().lower(),
            }
        )
    return result


class SongFormerStructureAdapter(StructureAdapter):
    """Mirror the official Hugging Face local-snapshot loading contract."""

    name = "songformer"
    engine = "songformer"

    def __init__(self, device: str = "cpu") -> None:
        super().__init__(device)
        self.model_id = os.environ.get("STRUCTURE_SONGFORMER_MODEL", "ASLP-lab/SongFormer")
        self._model: Any = None
        self._torch: Any = None
        self._local_dir: str | None = None

    def load(self) -> None:
        try:
            import torch
            from huggingface_hub import snapshot_download
            from transformers import AutoModel
        except ImportError as exc:
            raise RuntimeError(
                "SongFormer dependencies are not installed. Run this candidate in an "
                "isolated research environment rather than adding its stack to production."
            ) from exc

        configured_path = Path(self.model_id).expanduser()
        if configured_path.is_dir():
            local_dir = str(configured_path.resolve())
        else:
            local_dir = snapshot_download(
                repo_id=self.model_id,
                repo_type="model",
                allow_patterns="*",
                ignore_patterns=["SongFormer.pt", "SongFormer.safetensors"],
            )

        if local_dir not in sys.path:
            sys.path.append(local_dir)
        os.environ["SONGFORMER_LOCAL_DIR"] = local_dir

        self._torch = torch
        self._local_dir = local_dir
        self._model = AutoModel.from_pretrained(
            local_dir,
            trust_remote_code=True,
            low_cpu_mem_usage=False,
        )
        self._model.to(self.device)
        self._model.eval()
        self._loaded = True

    def analyze(self, audio_path: str) -> StructureResult:
        if not self._loaded:
            self.load()
        try:
            with self._torch.inference_mode():
                raw = self._model(audio_path)
            segments = _segments(raw)
            if not segments:
                return StructureResult(error="candidate returned no valid segments")
            return StructureResult(
                segments=segments,
                metadata={
                    "input_contract": "audio_file_path",
                    "upstream_sampling_rate_hz": 24000,
                },
            )
        except Exception as exc:
            return StructureResult(error=f"{type(exc).__name__}: {exc}")

    def metadata(self) -> StructureMetadata:
        try:
            transformers_version = version("transformers")
        except PackageNotFoundError:
            transformers_version = None
        return StructureMetadata(
            candidate=self.name,
            engine=self.engine,
            code_license="CC-BY-4.0",
            checkpoint_license=None,
            upstream_repo="https://github.com/ASLP-lab/SongFormer",
            upstream_version=transformers_version,
            checkpoint_name=self.model_id,
            training_datasets=_csv_env(
                "STRUCTURE_SONGFORMER_TRAINING_DATASETS",
                _SONGFORMER_RELEASED_TRAINING_FAMILIES,
            ),
            held_out_datasets=_csv_env("STRUCTURE_SONGFORMER_HELD_OUT_DATASETS"),
            training_partition=os.environ.get("STRUCTURE_SONGFORMER_TRAINING_PARTITION") or None,
            held_out_partition=os.environ.get("STRUCTURE_SONGFORMER_HELD_OUT_PARTITION") or None,
            split_source=os.environ.get("STRUCTURE_SONGFORMER_SPLIT_SOURCE") or None,
            notes=(
                "Official loading requires a local model snapshot on sys.path plus "
                "SONGFORMER_LOCAL_DIR and trust_remote_code. The one-click model card does not "
                "identify the exact released training mixture, while published SongFormer "
                "variants use HX with optional E/H/G SongFormDB families. Default provenance "
                "therefore treats every released training family as potentially overlapping; "
                "override only with checkpoint-specific lineage evidence. Checkpoint/commercial-"
                "use licensing also requires separate review."
            ),
        )
