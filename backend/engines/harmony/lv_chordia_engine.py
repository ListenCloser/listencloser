"""lv-chordia audio-native harmony engine.

Large-Vocabulary Chord Transcription via Chord Structure Decomposition.
MIT licensed, PyPI-installable, pretrained weights bundled.

Input modality: audio (WAV bytes)
Output: normalized chord timeline with root/quality/start/end

This engine is the primary chord-recognition path when audio is available.
music21 remains available for key analysis and symbolic theory interpretation.
"""

from __future__ import annotations

import logging
import os
import tempfile
import time
from typing import Any

from engines.base import EngineProvenance, HarmonyResult

logger = logging.getLogger("engines.harmony.lv_chordia")

# Chord labels from the submission dictionary (26 classes + N)
_CHORD_DICT_NAME = "submission"


def _lv_chordia_version() -> str:
    try:
        import lv_chordia
        return lv_chordia.__version__
    except Exception:
        return "unknown"


class LvChordiaHarmonyEngine:
    """Audio-native chord recognition engine using lv-chordia.

    This engine produces chord evidence directly from audio, bypassing
    MIDI transcription for chord detection. music21 remains available
    for key analysis and symbolic theory interpretation.
    """

    ENGINE = "lv-chordia"

    def __init__(self) -> None:
        pass

    @property
    def provenance(self) -> EngineProvenance:
        return EngineProvenance(
            engine=self.ENGINE,
            library_version=_lv_chordia_version(),
            model="ensemble_5models_hmm",
            parameters={"chord_dict": _CHORD_DICT_NAME},
        )

    def component_provenance(self) -> dict[str, EngineProvenance]:
        """Per-sub-capability provenance.

        lv-chordia delivers chords. Key/roman_numerals/cadences/voice_leading
        are not produced by this engine.
        """
        return {
            "chords": self.provenance,
        }

    def analyze(
        self,
        midi_bytes: bytes,
        tempo_bpm: float | None = None,
        audio_bytes: bytes | None = None,
        **kwargs: Any,
    ) -> HarmonyResult:
        """Analyze audio and return normalized chord timeline.

        Args:
            midi_bytes: MIDI bytes (unused by this engine, kept for protocol).
            tempo_bpm: Tempo in BPM (unused by this engine).
            audio_bytes: WAV audio bytes for chord recognition.
            **kwargs: Additional arguments (unused).

        Returns:
            HarmonyResult with chords populated, other fields empty.

        Raises:
            RuntimeError: If audio_bytes is None or lv-chordia fails.
        """
        if audio_bytes is None:
            raise RuntimeError(
                "lv-chordia requires audio input. No audio_bytes provided."
            )

        # Write audio to temp file (lv-chordia requires a file path)
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            f.write(audio_bytes)
            audio_path = f.name

        try:
            t0 = time.perf_counter()
            from lv_chordia.chord_recognition import chord_recognition
            raw_results = chord_recognition(
                audio_path=audio_path,
                chord_dict_name=_CHORD_DICT_NAME,
            )
            latency_ms = round((time.perf_counter() - t0) * 1000)
            logger.info(
                "lv_chordia_inference",
                extra={"latency_ms": latency_ms, "chord_count": len(raw_results)},
            )
        except Exception as e:
            raise RuntimeError(f"lv-chordia inference failed: {e}") from e
        finally:
            os.unlink(audio_path)

        # Convert to normalized chord format
        chords = []
        for ch in raw_results:
            root, quality = _parse_chord_label(ch["chord"])
            chords.append({
                "root": root,
                "quality": quality,
                "start": round(ch["start_time"], 3),
                "end": round(ch["end_time"], 3),
            })

        # Return HarmonyResult with chords only
        # Key/RN/cadences/voice_leading are NOT produced by this engine
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


def _parse_chord_label(label: str) -> tuple[str, str]:
    """Parse JAMS chord label like 'C:maj' into (root, quality).

    N (no chord) is returned as ('N', 'N') to represent passages
    without harmonic content. This is NOT a fake chord - it's a
    semantic marker for "no harmony detected."
    """
    if label == "N":
        return "N", "N"
    if ":" not in label:
        return label, "maj"  # fallback
    root, quality = label.split(":", 1)
    return root, quality
