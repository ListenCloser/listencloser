"""Isolated CLaMP3 text-to-audio passage retriever.

CLaMP3's audio path depends on MERT features. The released MERT checkpoint used
by upstream and by ListenCloser's historical foundation bakeoff has
non-commercial terms, so this adapter is intentionally INTERNAL_ONLY until the
full audio dependency chain is commercially deployable.

The normal API process never imports Torch/Transformers/CLaMP3. It verifies a
pinned checkout and local model assets, normalizes the exact source audio to a
24 kHz mono WAV, then invokes a separately provisioned Python runtime. Network
model/download access is disabled in the child process.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import tempfile
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

CLAMP3_UPSTREAM_REVISION = "9016d2b0c8d12d1aa79c2e0ab201e6822bdc83a8"
CLAMP3_MODEL = "CLaMP3-SAAS"
CLAMP3_MODEL_REPO = "sander-wood/clamp3"
CLAMP3_WEIGHT_FILENAME = (
    "weights_clamp3_saas_h_size_768_t_model_FacebookAI_xlm-roberta-base_"
    "t_length_128_a_size_768_a_layers_12_a_length_128_s_size_768_s_layers_12_"
    "p_size_64_p_length_512.pth"
)
CLAMP3_CODE_LICENSE = "MIT"
CLAMP3_WEIGHT_LICENSE = "MIT"
MERT_MODEL = "m-a-p/MERT-v1-95M"
MERT_WEIGHT_LICENSE = "CC-BY-NC-4.0"
TEXT_MODEL = "FacebookAI/xlm-roberta-base"

_DEFAULT_TIMEOUT_SECONDS = 30 * 60
_DEFAULT_WINDOW_SECONDS = 10.0
_DEFAULT_HOP_SECONDS = 5.0
_MAX_MATCHES = 5


@dataclass(frozen=True)
class CLaMP3PassageCandidate:
    start_seconds: float
    end_seconds: float
    similarity: float


@dataclass(frozen=True)
class CLaMP3RetrievalResult:
    candidates: tuple[CLaMP3PassageCandidate, ...]
    embedding_dim: int
    duration_seconds: float
    runtime_seconds: float | None
    provenance: dict[str, Any]


class CLaMP3TextAudioRetriever:
    """Run the official CLaMP3 audio/text model behind an isolated child runtime."""

    def __init__(
        self,
        *,
        runtime_python: str | None = None,
        checkout_path: str | None = None,
        weight_path: str | None = None,
        weight_sha256: str | None = None,
        mert_model_path: str | None = None,
        mert_dir_sha256: str | None = None,
        text_model_path: str | None = None,
        text_dir_sha256: str | None = None,
        ffmpeg_binary: str | None = None,
        timeout_seconds: float = _DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        if timeout_seconds <= 0:
            raise ValueError("CLaMP3 timeout must be positive")
        self._runtime_python = runtime_python or os.getenv("CLAMP3_RUNTIME_PYTHON")
        self._checkout_path = checkout_path or os.getenv("CLAMP3_CHECKOUT")
        self._weight_path = weight_path or os.getenv("CLAMP3_WEIGHT_PATH")
        self._weight_sha256 = weight_sha256 or os.getenv("CLAMP3_WEIGHT_SHA256")
        self._mert_model_path = mert_model_path or os.getenv("CLAMP3_MERT_MODEL_PATH")
        self._mert_dir_sha256 = mert_dir_sha256 or os.getenv("CLAMP3_MERT_DIR_SHA256")
        self._text_model_path = text_model_path or os.getenv("CLAMP3_TEXT_MODEL_PATH")
        self._text_dir_sha256 = text_dir_sha256 or os.getenv("CLAMP3_TEXT_DIR_SHA256")
        self._ffmpeg_binary = ffmpeg_binary or os.getenv("CLAMP3_FFMPEG", "ffmpeg")
        self._timeout_seconds = timeout_seconds
        self._verified = False

    @property
    def provenance(self) -> dict[str, Any]:
        return {
            "engine": "clamp3_text_audio",
            "model": CLAMP3_MODEL,
            "model_repo": CLAMP3_MODEL_REPO,
            "upstream_revision": CLAMP3_UPSTREAM_REVISION,
            "checkpoint_filename": CLAMP3_WEIGHT_FILENAME,
            "checkpoint_sha256": (self._weight_sha256 or "").lower() or None,
            "code_license": CLAMP3_CODE_LICENSE,
            "checkpoint_license": CLAMP3_WEIGHT_LICENSE,
            "audio_feature_model": MERT_MODEL,
            "audio_feature_model_asset_sha256": (self._mert_dir_sha256 or "").lower()
            or None,
            "audio_feature_model_license": MERT_WEIGHT_LICENSE,
            "text_model": TEXT_MODEL,
            "text_model_asset_sha256": (self._text_dir_sha256 or "").lower() or None,
            "commercial_default_eligible": False,
            "exposure": "INTERNAL_ONLY",
        }

    def _required_paths(self) -> tuple[Path, Path, Path, Path, Path]:
        missing = [
            name
            for name, value in (
                ("CLAMP3_RUNTIME_PYTHON", self._runtime_python),
                ("CLAMP3_CHECKOUT", self._checkout_path),
                ("CLAMP3_WEIGHT_PATH", self._weight_path),
                ("CLAMP3_WEIGHT_SHA256", self._weight_sha256),
                ("CLAMP3_MERT_MODEL_PATH", self._mert_model_path),
                ("CLAMP3_MERT_DIR_SHA256", self._mert_dir_sha256),
                ("CLAMP3_TEXT_MODEL_PATH", self._text_model_path),
                ("CLAMP3_TEXT_DIR_SHA256", self._text_dir_sha256),
            )
            if not value
        ]
        if missing:
            raise RuntimeError(
                "CLaMP3 isolated runtime is not fully pinned: " + ", ".join(missing)
            )

        runtime_python = Path(str(self._runtime_python))
        checkout = Path(str(self._checkout_path))
        weight_path = Path(str(self._weight_path))
        mert_path = Path(str(self._mert_model_path))
        text_path = Path(str(self._text_model_path))
        if not runtime_python.is_file():
            raise RuntimeError(f"CLaMP3 runtime Python not found: {runtime_python}")
        if not checkout.is_dir():
            raise RuntimeError(f"CLaMP3 checkout not found: {checkout}")
        if not weight_path.is_file():
            raise RuntimeError(f"CLaMP3 checkpoint not found: {weight_path}")
        if weight_path.name != CLAMP3_WEIGHT_FILENAME:
            raise RuntimeError("CLaMP3 checkpoint filename does not match the pinned SAAS asset")
        if not mert_path.is_dir():
            raise RuntimeError(f"CLaMP3 MERT model directory not found: {mert_path}")
        if not text_path.is_dir():
            raise RuntimeError(f"CLaMP3 text model directory not found: {text_path}")
        return runtime_python, checkout, weight_path, mert_path, text_path

    def _verify_assets(
        self,
        checkout: Path,
        weight_path: Path,
        mert_path: Path,
        text_path: Path,
    ) -> None:
        if self._verified:
            return
        completed = subprocess.run(
            ["git", "-C", str(checkout), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
        if completed.returncode != 0 or completed.stdout.strip() != CLAMP3_UPSTREAM_REVISION:
            raise RuntimeError(
                "CLaMP3 checkout revision mismatch; refusing an unpinned upstream runtime"
            )
        _verify_file_sha256(weight_path, str(self._weight_sha256))
        _verify_directory_sha256(mert_path, str(self._mert_dir_sha256))
        _verify_directory_sha256(text_path, str(self._text_dir_sha256))
        self._verified = True

    def retrieve(
        self,
        audio_bytes: bytes,
        query: str,
        *,
        max_matches: int = 3,
        window_seconds: float = _DEFAULT_WINDOW_SECONDS,
        hop_seconds: float = _DEFAULT_HOP_SECONDS,
    ) -> CLaMP3RetrievalResult:
        """Return bounded non-overlapping candidates for one exact source recording."""

        normalized_query = query.strip()
        if not normalized_query:
            raise ValueError("text query must not be empty")
        if len(normalized_query) > 500:
            raise ValueError("text query must be at most 500 characters")
        if not 1 <= max_matches <= _MAX_MATCHES:
            raise ValueError(f"max_matches must be between 1 and {_MAX_MATCHES}")
        if window_seconds <= 0 or hop_seconds <= 0 or hop_seconds > window_seconds:
            raise ValueError("window/hop policy is invalid")
        if not audio_bytes:
            raise ValueError("source audio is empty")

        runtime_python, checkout, weight_path, mert_path, text_path = self._required_paths()
        self._verify_assets(checkout, weight_path, mert_path, text_path)
        runtime_script = Path(__file__).with_name("clamp3_runtime.py")

        with tempfile.TemporaryDirectory(prefix="listencloser-clamp3-") as tmp:
            root = Path(tmp)
            source_path = root / "source.bin"
            normalized_path = root / "source.wav"
            query_path = root / "query.txt"
            result_path = root / "result.json"
            source_path.write_bytes(audio_bytes)
            query_path.write_text(normalized_query, encoding="utf-8")

            ffmpeg = subprocess.run(
                [
                    self._ffmpeg_binary,
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-y",
                    "-i",
                    str(source_path),
                    "-ac",
                    "1",
                    "-ar",
                    "24000",
                    str(normalized_path),
                ],
                capture_output=True,
                text=True,
                check=False,
                timeout=min(self._timeout_seconds, 120),
            )
            if ffmpeg.returncode != 0 or not normalized_path.is_file():
                raise RuntimeError("CLaMP3 source audio could not be normalized with ffmpeg")

            command = [
                str(runtime_python),
                str(runtime_script),
                "--checkout",
                str(checkout),
                "--weights",
                str(weight_path),
                "--mert-model",
                str(mert_path),
                "--text-model",
                str(text_path),
                "--audio",
                str(normalized_path),
                "--query",
                str(query_path),
                "--output",
                str(result_path),
                "--window-seconds",
                str(window_seconds),
                "--hop-seconds",
                str(hop_seconds),
                "--max-matches",
                str(max_matches),
            ]
            env = os.environ.copy()
            env.update(
                {
                    "HF_HUB_OFFLINE": "1",
                    "HF_DATASETS_OFFLINE": "1",
                    "TRANSFORMERS_OFFLINE": "1",
                }
            )
            try:
                completed = subprocess.run(
                    command,
                    capture_output=True,
                    text=True,
                    env=env,
                    check=False,
                    timeout=self._timeout_seconds,
                )
            except subprocess.TimeoutExpired as exc:
                raise RuntimeError("CLaMP3 passage retrieval timed out") from exc
            if completed.returncode != 0:
                stderr_tail = (completed.stderr or "")[-1500:]
                raise RuntimeError(
                    "CLaMP3 isolated runtime failed"
                    + (f": {stderr_tail}" if stderr_tail else "")
                )
            if not result_path.is_file():
                raise RuntimeError("CLaMP3 runtime completed without a result payload")
            try:
                payload = json.loads(result_path.read_text(encoding="utf-8"))
                candidates = tuple(
                    CLaMP3PassageCandidate(
                        start_seconds=float(item["start_seconds"]),
                        end_seconds=float(item["end_seconds"]),
                        similarity=float(item["similarity"]),
                    )
                    for item in payload["candidates"]
                )
                embedding_dim = int(payload["embedding_dim"])
                duration_seconds = float(payload["duration_seconds"])
                runtime_seconds_raw = payload.get("runtime_seconds")
                runtime_seconds = (
                    float(runtime_seconds_raw) if runtime_seconds_raw is not None else None
                )
            except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
                raise RuntimeError("CLaMP3 runtime returned a malformed result payload") from exc

        if embedding_dim <= 0 or duration_seconds <= 0:
            raise RuntimeError("CLaMP3 runtime returned invalid result metadata")
        for candidate in candidates:
            if not (
                0 <= candidate.start_seconds < candidate.end_seconds <= duration_seconds + 1e-3
            ):
                raise RuntimeError("CLaMP3 runtime returned an invalid passage locator")
            if not -1.000001 <= candidate.similarity <= 1.000001:
                raise RuntimeError("CLaMP3 runtime returned an invalid cosine similarity")

        return CLaMP3RetrievalResult(
            candidates=candidates,
            embedding_dim=embedding_dim,
            duration_seconds=duration_seconds,
            runtime_seconds=runtime_seconds,
            provenance={
                **self.provenance,
                "window_seconds": window_seconds,
                "hop_seconds": hop_seconds,
                "candidate_overlap_policy": "greedy_non_overlapping",
                "similarity": "cosine_in_clamp3_shared_space",
                "audio_normalization": "ffmpeg mono 24kHz PCM WAV",
            },
        )


def _verify_file_sha256(path: Path, expected: str) -> None:
    expected = expected.lower().strip()
    if len(expected) != 64:
        raise RuntimeError("expected checkpoint SHA-256 is malformed")
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    if digest.hexdigest() != expected:
        raise RuntimeError("CLaMP3 checkpoint SHA-256 mismatch")


def _directory_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    files = sorted(item for item in path.rglob("*") if item.is_file())
    if not files:
        raise RuntimeError(f"model directory is empty: {path}")
    for item in files:
        relative = item.relative_to(path).as_posix().encode("utf-8")
        digest.update(len(relative).to_bytes(8, "big"))
        digest.update(relative)
        with item.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    return digest.hexdigest()


def _verify_directory_sha256(path: Path, expected: str) -> None:
    expected = expected.lower().strip()
    if len(expected) != 64:
        raise RuntimeError("expected model-directory SHA-256 is malformed")
    if _directory_sha256(path) != expected:
        raise RuntimeError(f"model-directory SHA-256 mismatch: {path}")


@lru_cache(maxsize=1)
def default_clamp3_retriever() -> CLaMP3TextAudioRetriever:
    """Reuse verified asset identity across requests without retaining embeddings."""

    return CLaMP3TextAudioRetriever()


__all__ = [
    "CLAMP3_UPSTREAM_REVISION",
    "CLaMP3PassageCandidate",
    "CLaMP3RetrievalResult",
    "CLaMP3TextAudioRetriever",
    "default_clamp3_retriever",
]
