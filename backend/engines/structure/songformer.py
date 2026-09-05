"""Isolated SongFormer runtime boundary.

Official SongFormer inference is a GPU stack over SongFormer, MuQ and MusicFM.
The public MuQ checkpoint used upstream is CC BY-NC 4.0, so this adapter is
INTERNAL_ONLY under current rights. It deliberately does not register a product
capability or change the existing librosa Structure Map default.

The runtime directory is expected to be a pre-provisioned checkout of the pinned
upstream revision with SongFormer/MusicFM assets already fetched and verified.
MuQ must also be pre-cached in a dedicated Hugging Face home. Inference is forced
offline so a user-triggered job cannot mutate the model set.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from engines.base import EngineProvenance

SONGFORMER_UPSTREAM_REVISION = "139b2aa3b14bd1c6d961d0994e9fc975f1ef7fd5"
SONGFORMER_CODE_LICENSE = "CC-BY-4.0"
SONGFORMER_CHECKPOINT = "SongFormer.safetensors"
SONGFORMER_UPSTREAM_MD5 = "5a24800e12ab357744f8b47e523ba3e6"
MUSICFM_CHECKPOINT = "MusicFM/pretrained_msd.pt"
MUSICFM_UPSTREAM_MD5 = "df930aceac8209818556c4a656a0714c"
MUSICFM_STATS = "MusicFM/msd_stats.json"
MUSICFM_STATS_UPSTREAM_MD5 = "75ab2e47b093e07378f7f703bdb82c14"
MUQ_MODEL_ID = "OpenMuQ/MuQ-large-msd-iter"
MUQ_WEIGHT_LICENSE = "CC-BY-NC-4.0"
_INPUT_SAMPLE_RATE = 24000
_DEFAULT_TIMEOUT_SECONDS = 30 * 60


@dataclass(frozen=True)
class SongFormerSegment:
    start_seconds: float
    end_seconds: float
    label: str


@dataclass(frozen=True)
class SongFormerResult:
    segments: list[SongFormerSegment]
    provenance: EngineProvenance


class SongFormerEngine:
    """Run the official multi-model SongFormer inference script in isolation."""

    ENGINE = "songformer"

    def __init__(
        self,
        *,
        runtime_python: str | None = None,
        runtime_root: str | None = None,
        hf_home: str | None = None,
        muq_revision: str | None = None,
        cuda_visible_devices: str = "0",
        timeout_seconds: float = _DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        if timeout_seconds <= 0:
            raise ValueError("SongFormer timeout must be positive")
        self._runtime_python = runtime_python or os.getenv("SONGFORMER_RUNTIME_PYTHON")
        self._runtime_root = runtime_root or os.getenv("SONGFORMER_RUNTIME_ROOT")
        self._hf_home = hf_home or os.getenv("SONGFORMER_HF_HOME")
        self._muq_revision = muq_revision or os.getenv("SONGFORMER_MUQ_REVISION")
        self._cuda_visible_devices = cuda_visible_devices
        self._timeout_seconds = timeout_seconds

    @property
    def provenance(self) -> EngineProvenance:
        return EngineProvenance(
            engine=self.ENGINE,
            library_version=SONGFORMER_UPSTREAM_REVISION,
            model=SONGFORMER_CHECKPOINT,
            parameters={
                "runtime_classification": "INTERNAL_ONLY",
                "commercial_default_eligible": False,
                "upstream_revision": SONGFORMER_UPSTREAM_REVISION,
                "code_license": SONGFORMER_CODE_LICENSE,
                "songformer_upstream_md5": SONGFORMER_UPSTREAM_MD5,
                "musicfm_upstream_md5": MUSICFM_UPSTREAM_MD5,
                "musicfm_stats_upstream_md5": MUSICFM_STATS_UPSTREAM_MD5,
                "muq_model_id": MUQ_MODEL_ID,
                "muq_revision": self._muq_revision or "UNPINNED",
                "muq_weight_license": MUQ_WEIGHT_LICENSE,
                "input_sample_rate": _INPUT_SAMPLE_RATE,
                "cuda_visible_devices": self._cuda_visible_devices,
            },
        )

    def _runtime_paths(self) -> tuple[Path, Path, Path]:
        if not self._runtime_python:
            raise RuntimeError(
                "SongFormer requires SONGFORMER_RUNTIME_PYTHON pointing to the "
                "isolated pinned runtime"
            )
        if not self._runtime_root:
            raise RuntimeError(
                "SongFormer requires SONGFORMER_RUNTIME_ROOT pointing to the pinned checkout"
            )
        if not self._hf_home:
            raise RuntimeError(
                "SongFormer requires SONGFORMER_HF_HOME with the MuQ checkpoint pre-cached"
            )
        if not self._muq_revision:
            raise RuntimeError(
                "SongFormer requires SONGFORMER_MUQ_REVISION so the inherited MuQ asset "
                "identity is explicit"
            )

        runtime_python = Path(self._runtime_python)
        runtime_root = Path(self._runtime_root)
        hf_home = Path(self._hf_home)
        if not runtime_python.is_file():
            raise RuntimeError(f"SongFormer runtime Python not found: {runtime_python}")
        if not runtime_root.is_dir():
            raise RuntimeError(f"SongFormer runtime root not found: {runtime_root}")
        if not hf_home.is_dir():
            raise RuntimeError(f"SongFormer Hugging Face cache not found: {hf_home}")

        songformer_root = runtime_root / "src" / "SongFormer"
        infer_script = songformer_root / "infer" / "infer.py"
        if not infer_script.is_file():
            raise RuntimeError("SongFormer runtime root does not contain official infer/infer.py")
        _verify_md5(songformer_root / "ckpts" / SONGFORMER_CHECKPOINT, SONGFORMER_UPSTREAM_MD5)
        _verify_md5(songformer_root / "ckpts" / MUSICFM_CHECKPOINT, MUSICFM_UPSTREAM_MD5)
        _verify_md5(songformer_root / "ckpts" / MUSICFM_STATS, MUSICFM_STATS_UPSTREAM_MD5)
        return runtime_python, songformer_root, hf_home

    def analyze(self, audio_bytes: bytes, *, fmt: str = "wav") -> SongFormerResult:
        runtime_python, songformer_root, hf_home = self._runtime_paths()
        if not audio_bytes:
            raise ValueError("SongFormer requires non-empty audio bytes")
        source_format = str(fmt or "wav").lower().lstrip(".")
        if source_format not in {"wav", "mp3", "m4a", "flac", "ogg"}:
            raise ValueError(f"unsupported SongFormer input format: {source_format}")

        with tempfile.TemporaryDirectory(prefix="listencloser-songformer-") as tmp:
            root = Path(tmp)
            input_audio = root / f"source.{source_format}"
            input_list = root / "inputs.scp"
            output_dir = root / "outputs"
            input_audio.write_bytes(audio_bytes)
            input_list.write_text(f"{input_audio}\n", encoding="utf-8")
            output_dir.mkdir()

            command = [
                str(runtime_python),
                "infer/infer.py",
                "--input_path",
                str(input_list),
                "--output_path",
                str(output_dir),
                "--gpu_num",
                "1",
                "--num_thread_per_gpu",
                "1",
                "--model",
                "SongFormer",
                "--checkpoint",
                SONGFORMER_CHECKPOINT,
                "--config_path",
                "SongFormer.yaml",
            ]
            env = os.environ.copy()
            env["HF_HOME"] = str(hf_home)
            env["HF_HUB_OFFLINE"] = "1"
            env["TRANSFORMERS_OFFLINE"] = "1"
            env["CUDA_VISIBLE_DEVICES"] = self._cuda_visible_devices
            third_party = songformer_root.parent / "third_party"
            existing_pythonpath = env.get("PYTHONPATH", "")
            env["PYTHONPATH"] = os.pathsep.join(
                part for part in (str(third_party), str(songformer_root), existing_pythonpath) if part
            )

            try:
                completed = subprocess.run(
                    command,
                    cwd=songformer_root,
                    capture_output=True,
                    text=True,
                    env=env,
                    timeout=self._timeout_seconds,
                    check=False,
                )
            except subprocess.TimeoutExpired as exc:
                raise RuntimeError("SongFormer inference timed out") from exc

            if completed.returncode != 0:
                stderr_tail = (completed.stderr or "")[-1500:]
                raise RuntimeError(
                    "SongFormer isolated runtime failed"
                    + (f": {stderr_tail}" if stderr_tail else "")
                )

            result_path = output_dir / "source.json"
            if not result_path.is_file():
                # Upstream catches per-file inference exceptions internally, so a
                # zero process exit without the expected JSON is still failure.
                raise RuntimeError("SongFormer completed without producing structure JSON")
            segments = _parse_segments(result_path)
            if not segments:
                raise RuntimeError("SongFormer produced an empty structure result")

        return SongFormerResult(segments=segments, provenance=self.provenance)


def _verify_md5(path: Path, expected: str) -> None:
    if not path.is_file():
        raise RuntimeError(f"required SongFormer asset not found: {path}")
    digest = hashlib.md5(usedforsecurity=False)
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    if digest.hexdigest() != expected:
        raise RuntimeError(f"SongFormer asset checksum mismatch: {path.name}")


def _parse_segments(path: Path) -> list[SongFormerSegment]:
    raw: Any = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise RuntimeError("SongFormer structure JSON must be a list")
    segments: list[SongFormerSegment] = []
    previous_end = 0.0
    for item in raw:
        if not isinstance(item, dict):
            raise RuntimeError("SongFormer structure JSON contains a non-object segment")
        start = float(item["start"])
        end = float(item["end"])
        label = str(item["label"]).strip()
        if start < 0 or end <= start or start < previous_end or not label:
            raise RuntimeError("SongFormer emitted invalid or non-monotonic segments")
        segments.append(SongFormerSegment(start_seconds=start, end_seconds=end, label=label))
        previous_end = end
    return segments
