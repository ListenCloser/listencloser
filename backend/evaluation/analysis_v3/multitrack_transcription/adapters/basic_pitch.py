"""Adapters that exercise existing hello-ai transcription engines without production changes."""

from __future__ import annotations

import resource
import time
from pathlib import Path
from typing import Any


def _max_rss_mb() -> float:
    value = float(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    # Linux reports KiB; macOS reports bytes. Evaluation runners are expected to
    # record platform metadata, so normalize conservatively by magnitude.
    return round(value / (1024.0 * 1024.0) if value > 10_000_000 else value / 1024.0, 2)


def run_basic_pitch(audio_path: Path, output_midi: Path) -> dict[str, Any]:
    """Run the repository's production BasicPitchEngine on one audio file."""

    from engines.transcription.basic_pitch import BasicPitchEngine

    audio = audio_path.read_bytes()
    engine = BasicPitchEngine()
    started = time.perf_counter()
    result = engine.transcribe(audio, fmt=audio_path.suffix.lstrip("."))
    elapsed = time.perf_counter() - started

    output_midi.parent.mkdir(parents=True, exist_ok=True)
    output_midi.write_bytes(result.midi)
    return {
        "runtime_seconds": round(elapsed, 3),
        "process_max_rss_mb": _max_rss_mb(),
        "predicted_notes": result.num_notes,
        "provenance": result.provenance.to_dict(),
        "program_attribution": "none; Basic Pitch output is instrument-agnostic",
        "drum_attribution": "unsupported",
    }
