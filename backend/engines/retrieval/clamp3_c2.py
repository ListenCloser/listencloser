"""Pinned CLaMP3 C2 text-to-performance passage retriever.

C2 is the symbolic CLaMP3 checkpoint recommended upstream for MIDI and sheet
music retrieval. This adapter intentionally consumes performance MIDI rather
than raw audio, avoiding the MERT dependency used by CLaMP3 SAAS. Exact
source-audio authority is enforced by the domain layer: the performance Version
must be directly parented to the source audio Version whose timeline receives
the returned locators.
"""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
from functools import lru_cache
from pathlib import Path

from engines.retrieval.clamp3 import (
    CLAMP3_CODE_LICENSE,
    CLAMP3_MODEL_REPO,
    CLAMP3_UPSTREAM_REVISION,
    CLAMP3_WEIGHT_LICENSE,
    TEXT_MODEL,
    CLaMP3PassageCandidate,
    CLaMP3RetrievalResult,
    _verify_directory_sha256,
    _verify_file_sha256,
)

CLAMP3_C2_MODEL = "CLaMP3-C2"
CLAMP3_C2_WEIGHT_FILENAME = (
    "weights_clamp3_c2_h_size_768_t_model_FacebookAI_xlm-roberta-base_"
    "t_length_128_a_size_768_a_layers_12_a_length_128_s_size_768_s_layers_12_"
    "p_size_64_p_length_512.pth"
)

_DEFAULT_TIMEOUT_SECONDS = 30 * 60
_DEFAULT_WINDOW_SECONDS = 10.0
_DEFAULT_HOP_SECONDS = 5.0
_MAX_MATCHES = 5


class CLaMP3TextPerformanceRetriever:
    """Run CLaMP3 C2 over performance MIDI in an isolated offline runtime."""

    def __init__(
        self,
        *,
        runtime_python: str | None = None,
        checkout_path: str | None = None,
        weight_path: str | None = None,
        weight_sha256: str | None = None,
        text_model_path: str | None = None,
        text_dir_sha256: str | None = None,
        timeout_seconds: float = _DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        if timeout_seconds <= 0:
            raise ValueError("CLaMP3 C2 timeout must be positive")
        self._runtime_python = runtime_python or os.getenv("CLAMP3_RUNTIME_PYTHON")
        self._checkout_path = checkout_path or os.getenv("CLAMP3_CHECKOUT")
        self._weight_path = weight_path or os.getenv("CLAMP3_C2_WEIGHT_PATH")
        self._weight_sha256 = weight_sha256 or os.getenv("CLAMP3_C2_WEIGHT_SHA256")
        self._text_model_path = text_model_path or os.getenv("CLAMP3_TEXT_MODEL_PATH")
        self._text_dir_sha256 = text_dir_sha256 or os.getenv("CLAMP3_TEXT_DIR_SHA256")
        self._timeout_seconds = timeout_seconds
        self._verified = False

    @property
    def provenance(self) -> dict[str, object]:
        return {
            "engine": "clamp3_text_performance",
            "model": CLAMP3_C2_MODEL,
            "model_repo": CLAMP3_MODEL_REPO,
            "upstream_revision": CLAMP3_UPSTREAM_REVISION,
            "checkpoint_filename": CLAMP3_C2_WEIGHT_FILENAME,
            "checkpoint_sha256": (self._weight_sha256 or "").lower() or None,
            "code_license": CLAMP3_CODE_LICENSE,
            "checkpoint_license": CLAMP3_WEIGHT_LICENSE,
            "text_model": TEXT_MODEL,
            "text_model_asset_sha256": (self._text_dir_sha256 or "").lower() or None,
            "music_modality": "performance_midi_mtf",
            "rights_classification": "permissive",
            "canonical_default": False,
        }

    def _required_paths(self) -> tuple[Path, Path, Path, Path]:
        missing = [
            name
            for name, value in (
                ("CLAMP3_RUNTIME_PYTHON", self._runtime_python),
                ("CLAMP3_CHECKOUT", self._checkout_path),
                ("CLAMP3_C2_WEIGHT_PATH", self._weight_path),
                ("CLAMP3_C2_WEIGHT_SHA256", self._weight_sha256),
                ("CLAMP3_TEXT_MODEL_PATH", self._text_model_path),
                ("CLAMP3_TEXT_DIR_SHA256", self._text_dir_sha256),
            )
            if not value
        ]
        if missing:
            raise RuntimeError("CLaMP3 C2 runtime is not fully pinned: " + ", ".join(missing))

        runtime_python = Path(str(self._runtime_python))
        checkout = Path(str(self._checkout_path))
        weight_path = Path(str(self._weight_path))
        text_path = Path(str(self._text_model_path))
        if not runtime_python.is_file():
            raise RuntimeError(f"CLaMP3 C2 runtime Python not found: {runtime_python}")
        if not checkout.is_dir():
            raise RuntimeError(f"CLaMP3 checkout not found: {checkout}")
        if not weight_path.is_file():
            raise RuntimeError(f"CLaMP3 C2 checkpoint not found: {weight_path}")
        if weight_path.name != CLAMP3_C2_WEIGHT_FILENAME:
            raise RuntimeError("CLaMP3 C2 checkpoint filename does not match the pinned asset")
        if not text_path.is_dir():
            raise RuntimeError(f"CLaMP3 text model directory not found: {text_path}")
        return runtime_python, checkout, weight_path, text_path

    def _verify_assets(self, checkout: Path, weight_path: Path, text_path: Path) -> None:
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
        _verify_directory_sha256(text_path, str(self._text_dir_sha256))
        self._verified = True

    def retrieve(
        self,
        midi_bytes: bytes,
        query: str,
        *,
        max_matches: int = 3,
        window_seconds: float = _DEFAULT_WINDOW_SECONDS,
        hop_seconds: float = _DEFAULT_HOP_SECONDS,
    ) -> CLaMP3RetrievalResult:
        """Return bounded source-time candidates derived from performance MIDI."""

        normalized_query = query.strip()
        if not normalized_query:
            raise ValueError("text query must not be empty")
        if len(normalized_query) > 500:
            raise ValueError("text query must be at most 500 characters")
        if not 1 <= max_matches <= _MAX_MATCHES:
            raise ValueError(f"max_matches must be between 1 and {_MAX_MATCHES}")
        if window_seconds <= 0 or hop_seconds <= 0 or hop_seconds > window_seconds:
            raise ValueError("window/hop policy is invalid")
        if not midi_bytes:
            raise ValueError("performance MIDI is empty")

        runtime_python, checkout, weight_path, text_path = self._required_paths()
        self._verify_assets(checkout, weight_path, text_path)
        runtime_script = Path(__file__).with_name("clamp3_c2_runtime.py")

        with tempfile.TemporaryDirectory(prefix="listencloser-clamp3-c2-") as tmp:
            root = Path(tmp)
            midi_path = root / "performance.mid"
            query_path = root / "query.txt"
            result_path = root / "result.json"
            midi_path.write_bytes(midi_bytes)
            query_path.write_text(normalized_query, encoding="utf-8")

            command = [
                str(runtime_python),
                str(runtime_script),
                "--checkout",
                str(checkout),
                "--weights",
                str(weight_path),
                "--text-model",
                str(text_path),
                "--midi",
                str(midi_path),
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
                raise RuntimeError("CLaMP3 C2 passage retrieval timed out") from exc
            if completed.returncode != 0:
                stderr_tail = (completed.stderr or "")[-1500:]
                raise RuntimeError(
                    "CLaMP3 C2 isolated runtime failed"
                    + (f": {stderr_tail}" if stderr_tail else "")
                )
            if not result_path.is_file():
                raise RuntimeError("CLaMP3 C2 runtime completed without a result payload")
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
                raise RuntimeError("CLaMP3 C2 runtime returned a malformed result payload") from exc

        if embedding_dim <= 0 or duration_seconds <= 0:
            raise RuntimeError("CLaMP3 C2 runtime returned invalid result metadata")
        for candidate in candidates:
            if not (
                0 <= candidate.start_seconds < candidate.end_seconds <= duration_seconds + 1e-3
            ):
                raise RuntimeError("CLaMP3 C2 runtime returned an invalid passage locator")
            if not -1.000001 <= candidate.similarity <= 1.000001:
                raise RuntimeError("CLaMP3 C2 runtime returned an invalid cosine similarity")

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
                "symbolic_preprocessing": "upstream-compatible M3 MIDI Text Format",
                "locator_timeline": "direct-parent performance seconds",
            },
        )


@lru_cache(maxsize=1)
def default_clamp3_c2_retriever() -> CLaMP3TextPerformanceRetriever:
    """Reuse verified C2 asset identity without retaining passage embeddings."""

    return CLaMP3TextPerformanceRetriever()


__all__ = [
    "CLAMP3_C2_MODEL",
    "CLAMP3_C2_WEIGHT_FILENAME",
    "CLaMP3TextPerformanceRetriever",
    "default_clamp3_c2_retriever",
]
