"""Experimental ChordMini audio-native harmony engine.

ChordMini is an alternate interpretation only. It never silently replaces the
current lv-chordia route and it emits chord spans only; key, Roman numeral,
cadence, and voice-leading claims remain outside this engine's contract.
"""

from __future__ import annotations

import os
import tempfile
import time
from pathlib import Path
from typing import Any

from engines.base import EngineProvenance, HarmonyResult

_ENGINE = "chordmini"
_UPSTREAM_COMMIT = "aa6e3a8d7b017f082fd2aaff9329d5c26af49c03"
_CHECKPOINT_GIT_BLOB_SHA = "b61f6b3a02cc42b87afa38392f80d185a49f719a"
_CHECKPOINT_NAME = "2e1d_model_best.pth"


def _normalize_chord_label(label: str) -> tuple[str, str]:
    """Normalize ChordMini's 170-class label to ListenCloser chord fields."""
    if label == "N":
        return "N", "N"
    if label == "X":
        return "X", "X"
    if ":" not in label:
        return label, "maj"
    root, quality = label.split(":", 1)
    return root, quality


class ChordMiniHarmonyEngine:
    """Run the pinned ChordMini 2E1D checkpoint as an explicit challenger."""

    ENGINE = _ENGINE

    def __init__(self, checkpoint_path: str | None = None) -> None:
        self._checkpoint_path = checkpoint_path or os.getenv("CHORDMINI_CHECKPOINT_PATH")
        self._last_provenance: EngineProvenance | None = None

    @property
    def provenance(self) -> EngineProvenance:
        if self._last_provenance is not None:
            return self._last_provenance
        return EngineProvenance(
            engine=self.ENGINE,
            library_version=_UPSTREAM_COMMIT,
            model=_CHECKPOINT_NAME,
            parameters={
                "checkpoint_git_blob_sha": _CHECKPOINT_GIT_BLOB_SHA,
                "runtime": "vendored-minimal-inference",
                "experimental": True,
            },
        )

    def component_provenance(self) -> dict[str, EngineProvenance]:
        return {"chords": self.provenance}

    def analyze(
        self,
        midi_bytes: bytes,
        tempo_bpm: float | None = None,
        audio_bytes: bytes | None = None,
        **kwargs: Any,
    ) -> HarmonyResult:
        del midi_bytes, tempo_bpm, kwargs
        if audio_bytes is None:
            raise RuntimeError("ChordMini requires audio input. No audio_bytes provided.")

        try:
            from engines.harmony._chordmini_runtime import infer_chords
            from engines.harmony.chordmini_assets import checkpoint_source_url, resolve_checkpoint
        except ImportError as exc:
            raise RuntimeError(
                "ChordMini runtime dependencies are unavailable. "
                "Install the backend worker dependency group."
            ) from exc

        checkpoint_path = resolve_checkpoint(self._checkpoint_path)
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as handle:
            handle.write(audio_bytes)
            audio_path = handle.name

        started = time.perf_counter()
        try:
            inference = infer_chords(audio_path, checkpoint_path)
        except Exception as exc:
            raise RuntimeError(f"ChordMini inference failed: {exc}") from exc
        finally:
            Path(audio_path).unlink(missing_ok=True)

        runtime_ms = round((time.perf_counter() - started) * 1000)
        chords: list[dict[str, Any]] = []
        for start, end, label in inference.segments:
            root, quality = _normalize_chord_label(label)
            chords.append(
                {
                    "root": root,
                    "quality": quality,
                    "start": round(float(start), 3),
                    "end": round(float(end), 3),
                }
            )

        self._last_provenance = EngineProvenance(
            engine=self.ENGINE,
            library_version=_UPSTREAM_COMMIT,
            model=_CHECKPOINT_NAME,
            parameters={
                "checkpoint_git_blob_sha": _CHECKPOINT_GIT_BLOB_SHA,
                "checkpoint_sha256": inference.checkpoint_sha256,
                "checkpoint_source": checkpoint_source_url(),
                "sample_rate": 22_050,
                "hop_length": 2_048,
                "n_bins": 144,
                "bins_per_octave": 24,
                "sequence_length": 108,
                "overlap_ratio": 0.5,
                "smoothing_kernel": 9,
                "frame_duration": inference.frame_duration,
                "frame_count": inference.frame_count,
                "runtime_ms": runtime_ms,
                "experimental": True,
            },
        )

        return HarmonyResult(
            key=None,
            chords=chords,
            roman_numerals=[],
            cadences=[],
            voice_leading=None,
            phrases=[],
            provenance=self.provenance,
            component_provenance=self.component_provenance(),
        )
