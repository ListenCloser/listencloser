"""Isolated AnalysisGNN runtime for trusted symbolic scores.

The upstream package has a research-shaped PyTorch/PyG/GraphMuse environment and
can download a W&B artifact implicitly. ListenCloser does neither in its normal
worker. This adapter accepts only a pre-provisioned isolated Python environment
and a local checkpoint with an expected SHA-256, then invokes upstream prediction
with explicit ``--checkpoint_path`` and ``--input_score`` arguments.

The public repository is MIT. The exact default pretrained artifact's
redistribution/commercial terms are not stated in the repository, so this path
remains INTERNAL_ONLY until those model terms are independently pinned.
"""

from __future__ import annotations

import csv
import hashlib
import os
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from engines.base import EngineProvenance

ANALYSISGNN_UPSTREAM_REVISION = "e115182fb29b74bdcb6bf3547ed427d967580947"
ANALYSISGNN_PACKAGE_VERSION = "1.0.0"
ANALYSISGNN_DEFAULT_ARTIFACT = "melkisedeath/AnalysisGNN/model-uvj2ddun:v1"
ANALYSISGNN_CODE_LICENSE = "MIT"
ANALYSISGNN_MODEL_LICENSE = "UNVERIFIED"
DEFAULT_TASKS = (
    "cadence",
    "localkey",
    "quality",
    "root",
    "bass",
    "inversion",
    "degree1",
    "degree2",
    "romanNumeral",
)
_DEFAULT_TIMEOUT_SECONDS = 10 * 60


@dataclass(frozen=True)
class AnalysisGNNResult:
    predictions: list[dict[str, str]]
    tasks: tuple[str, ...]
    provenance: EngineProvenance


class AnalysisGNNEngine:
    """Run official AnalysisGNN prediction against one trusted MusicXML input."""

    ENGINE = "analysisgnn"

    def __init__(
        self,
        *,
        runtime_python: str | None = None,
        checkpoint_path: str | None = None,
        checkpoint_sha256: str | None = None,
        device: str = "cpu",
        timeout_seconds: float = _DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        if timeout_seconds <= 0:
            raise ValueError("AnalysisGNN timeout must be positive")
        self._runtime_python = runtime_python or os.getenv("ANALYSISGNN_RUNTIME_PYTHON")
        self._checkpoint_path = checkpoint_path or os.getenv("ANALYSISGNN_CHECKPOINT_PATH")
        self._checkpoint_sha256 = checkpoint_sha256 or os.getenv("ANALYSISGNN_CHECKPOINT_SHA256")
        self._device = device
        self._timeout_seconds = timeout_seconds
        self._verified_checkpoint: tuple[str, int, int] | None = None

    @property
    def provenance(self) -> EngineProvenance:
        parameters: dict[str, Any] = {
            "device": self._device,
            "isolated_runtime": True,
            "upstream_revision": ANALYSISGNN_UPSTREAM_REVISION,
            "upstream_default_artifact": ANALYSISGNN_DEFAULT_ARTIFACT,
            "code_license": ANALYSISGNN_CODE_LICENSE,
            "model_license": ANALYSISGNN_MODEL_LICENSE,
            "runtime_classification": "INTERNAL_ONLY",
            "commercial_default_eligible": False,
        }
        if self._checkpoint_sha256:
            parameters["checkpoint_sha256"] = self._checkpoint_sha256.lower()
        return EngineProvenance(
            engine=self.ENGINE,
            library_version=ANALYSISGNN_PACKAGE_VERSION,
            model="local-pinned-checkpoint",
            parameters=parameters,
        )

    def _runtime_paths(self) -> tuple[Path, Path]:
        if not self._runtime_python:
            raise RuntimeError(
                "AnalysisGNN requires ANALYSISGNN_RUNTIME_PYTHON pointing to the "
                "isolated pinned runtime"
            )
        if not self._checkpoint_path:
            raise RuntimeError(
                "AnalysisGNN requires ANALYSISGNN_CHECKPOINT_PATH; implicit W&B "
                "artifact download is not allowed"
            )
        if not self._checkpoint_sha256:
            raise RuntimeError(
                "AnalysisGNN requires ANALYSISGNN_CHECKPOINT_SHA256 so model identity "
                "is fail-closed"
            )
        runtime_python = Path(self._runtime_python)
        checkpoint = Path(self._checkpoint_path)
        if not runtime_python.is_file():
            raise RuntimeError(f"AnalysisGNN runtime Python not found: {runtime_python}")
        if not checkpoint.is_file():
            raise RuntimeError(f"AnalysisGNN checkpoint not found: {checkpoint}")
        self._verify_checkpoint(checkpoint)
        return runtime_python, checkpoint

    def _verify_checkpoint(self, checkpoint: Path) -> None:
        stat = checkpoint.stat()
        cache_key = (str(checkpoint.resolve()), stat.st_size, stat.st_mtime_ns)
        if self._verified_checkpoint == cache_key:
            return
        digest = hashlib.sha256()
        with checkpoint.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        if digest.hexdigest() != str(self._checkpoint_sha256).lower():
            raise RuntimeError(
                "AnalysisGNN checkpoint SHA-256 mismatch; refusing to run an "
                "unpinned model asset"
            )
        self._verified_checkpoint = cache_key

    def analyze_musicxml(
        self,
        musicxml_bytes: bytes,
        *,
        tasks: tuple[str, ...] = DEFAULT_TASKS,
    ) -> AnalysisGNNResult:
        runtime_python, checkpoint = self._runtime_paths()
        normalized_tasks = _normalize_tasks(tasks)
        if not musicxml_bytes.strip():
            raise ValueError("AnalysisGNN requires non-empty MusicXML bytes")

        with tempfile.TemporaryDirectory(prefix="listencloser-analysisgnn-") as tmp:
            root = Path(tmp)
            input_path = root / "score.musicxml"
            output_dir = root / "outputs"
            input_path.write_bytes(musicxml_bytes)
            output_dir.mkdir()

            command = [
                str(runtime_python),
                "-m",
                "analysisgnn.inference.predict_analysis",
                "--checkpoint_path",
                str(checkpoint),
                "--input_score",
                str(input_path),
                "--output_dir",
                str(output_dir),
                "--tasks",
                ",".join(normalized_tasks),
                "--device",
                self._device,
                "--export_csv",
            ]
            env = os.environ.copy()
            env["WANDB_MODE"] = "offline"
            env["WANDB_DISABLED"] = "true"

            try:
                completed = subprocess.run(
                    command,
                    capture_output=True,
                    text=True,
                    env=env,
                    timeout=self._timeout_seconds,
                    check=False,
                )
            except subprocess.TimeoutExpired as exc:
                raise RuntimeError("AnalysisGNN inference timed out") from exc

            if completed.returncode != 0:
                stderr_tail = (completed.stderr or "")[-1500:]
                raise RuntimeError(
                    "AnalysisGNN isolated runtime failed"
                    + (f": {stderr_tail}" if stderr_tail else "")
                )

            csv_path = output_dir / "score_analysis.csv"
            if not csv_path.is_file():
                raise RuntimeError("AnalysisGNN completed without producing analysis CSV")
            predictions = _read_predictions(csv_path)
            if not predictions:
                raise RuntimeError("AnalysisGNN produced an empty analysis CSV")

        return AnalysisGNNResult(
            predictions=predictions,
            tasks=normalized_tasks,
            provenance=self.provenance,
        )


def _normalize_tasks(tasks: tuple[str, ...]) -> tuple[str, ...]:
    normalized = tuple(dict.fromkeys(task.strip() for task in tasks if task.strip()))
    if not normalized:
        raise ValueError("AnalysisGNN requires at least one task")
    return normalized


def _read_predictions(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]
