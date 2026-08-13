"""Engine evaluation framework for OSS music model bakeoff.

This module provides a uniform interface for evaluating candidate OSS engines
against the existing evaluation infrastructure. It does NOT change production
routing — production code continues to use the existing engine seams.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Protocol, Literal

from evaluation.corpus import EvalClip
from evaluation.models import Reference


EngineCategory = Literal[
    "transcription",
    "beat_tracking",
    "harmony",
    "structure",
]


@dataclass(frozen=True)
class EngineInfo:
    """Static metadata about an OSS engine candidate."""
    name: str
    category: EngineCategory
    repo_url: str
    license: str
    install_cmd: str  # pip install command or equivalent
    model_size_mb: float | None = None
    requires_gpu: bool = False
    python_version: str = ">=3.10"
    notes: str = ""


@dataclass(frozen=True)
class EngineEvalResult:
    """Result of evaluating one engine on one clip."""
    engine_name: str
    clip_id: str
    category: EngineCategory
    success: bool
    output: dict[str, Any] | None = None
    metrics: dict[str, Any] | None = None
    runtime_s: float = 0.0
    peak_memory_mb: float = 0.0
    error: str | None = None
    # Engine-specific diagnostics
    diagnostics: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class EngineAggregateReport:
    """Aggregated evaluation across a corpus for one engine."""
    engine_name: str
    category: EngineCategory
    engine_info: EngineInfo
    clips_total: int
    clips_succeeded: int
    clips_failed: int
    avg_runtime_s: float
    avg_peak_memory_mb: float
    # Category-specific aggregate metrics
    aggregate_metrics: dict[str, Any]
    failure_cases: list[dict[str, Any]] = field(default_factory=list)


class EngineAdapter(Protocol):
    """Protocol for engine evaluation adapters.
    
    Adapters wrap OSS engines and present a uniform interface for evaluation.
    They must NOT be used in production code paths.
    """
    engine_info: EngineInfo

    def is_available(self) -> bool:
        """Check if engine can be imported/loaded."""
        ...

    def prepare(self) -> None:
        """One-time setup (model download, compilation, etc.)."""
        ...

    def transcribe(self, audio_bytes: bytes, sample_rate: int = 44100, **kwargs) -> dict[str, Any]:
        """Transcribe audio to MIDI/notes. For transcription engines."""
        ...

    def estimate_beats(self, audio_bytes: bytes, sample_rate: int = 44100, **kwargs) -> dict[str, Any]:
        """Estimate beats/downbeats. For beat tracking engines."""
        ...

    def analyze_harmony(self, midi_bytes: bytes, **kwargs) -> dict[str, Any]:
        """Analyze harmony from MIDI. For harmony engines."""
        ...

    def analyze_structure(self, audio_bytes: bytes, **kwargs) -> dict[str, Any]:
        """Analyze structure from audio. For structure engines."""
        ...

    def cleanup(self) -> None:
        """Optional cleanup (GPU memory, temp files)."""
        ...


def measure_resources(func):
    """Decorator to measure runtime and peak memory of a function."""
    def wrapper(*args, **kwargs):
        import tracemalloc
        tracemalloc.start()
        t0 = time.monotonic()
        try:
            result = func(*args, **kwargs)
            return result
        finally:
            elapsed = time.monotonic() - t0
            current, peak = tracemalloc.get_traced_memory()
            tracemalloc.stop()
            if hasattr(result, '__dict__'):
                result.runtime_s = elapsed
                result.peak_memory_mb = peak / (1024 * 1024)
            elif isinstance(result, dict):
                result["runtime_s"] = elapsed
                result["peak_memory_mb"] = peak / (1024 * 1024)
    return wrapper


def run_engine_evaluation(
    adapter: EngineAdapter,
    clips: list[EvalClip],
    category: EngineCategory,
    output_dir: str,
    **adapter_kwargs,
) -> EngineAggregateReport:
    """Run an engine adapter across a corpus and aggregate results."""
    import os
    import json
    import time
    import tracemalloc
    from pathlib import Path

    os.makedirs(output_dir, exist_ok=True)

    clip_results: list[EngineEvalResult] = []

    for clip in clips:
        clip_result = _run_clip_on_engine(adapter, clip, category, **adapter_kwargs)
        clip_results.append(clip_result)

        # Write per-clip result
        clip_path = Path(output_dir) / f"{adapter.engine_info.name}_{clip.id}.json"
        with open(clip_path, "w") as f:
            json.dump(clip_result.__dict__, f, indent=2, default=str)

    return _aggregate_results(adapter, clip_results, category)


def _run_clip_on_engine(
    adapter: EngineAdapter,
    clip: EvalClip,
    category: EngineCategory,
    **adapter_kwargs,
) -> EngineEvalResult:
    """Run a single clip through the engine adapter."""
    import os
    import time
    import tracemalloc
    from pathlib import Path

    # Measure runtime and memory
    tracemalloc.start()
    t0 = time.monotonic()

    result = EngineEvalResult(
        engine_name=adapter.engine_info.name,
        clip_id=clip.id,
        category=category,
        success=False,
    )

    try:
        if not adapter.is_available():
            raise RuntimeError(f"Engine {adapter.engine_info.name} not available")

        adapter.prepare()

        if category == "transcription":
            audio_bytes = Path(clip.audio).read_bytes()
            output = adapter.transcribe(audio_bytes, **adapter_kwargs)
            metrics = _compute_transcription_metrics(output, clip)

        elif category == "beat_tracking":
            audio_bytes = Path(clip.audio).read_bytes()
            output = adapter.estimate_beats(audio_bytes, **adapter_kwargs)
            metrics = _compute_beat_metrics(output, clip)

        elif category == "harmony":
            if not clip.reference_midi:
                raise RuntimeError("Harmony evaluation requires reference MIDI")
            midi_bytes = Path(clip.reference_midi).read_bytes()
            output = adapter.analyze_harmony(midi_bytes, **adapter_kwargs)
            metrics = _compute_harmony_metrics(output, clip)

        elif category == "structure":
            audio_bytes = Path(clip.audio).read_bytes()
            output = adapter.analyze_structure(audio_bytes, **adapter_kwargs)
            metrics = _compute_structure_metrics(output, clip)

        else:
            raise ValueError(f"Unknown category: {category}")

        elapsed = time.monotonic() - t0
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        result = EngineEvalResult(
            engine_name=adapter.engine_info.name,
            clip_id=clip.id,
            category=category,
            success=True,
            output=output,
            metrics=metrics,
            runtime_s=elapsed,
            peak_memory_mb=peak / (1024 * 1024),
        )

    except Exception as e:
        elapsed = time.monotonic() - t0
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        result = EngineEvalResult(
            engine_name=adapter.engine_info.name,
            clip_id=clip.id,
            category=category,
            success=False,
            error=str(e),
            runtime_s=elapsed,
            peak_memory_mb=peak / (1024 * 1024),
        )

    return result


def _compute_transcription_metrics(output: dict[str, Any], clip: EvalClip) -> dict[str, Any]:
    """Compute transcription metrics against reference."""
    if not clip.reference_midi:
        return {}

    from evaluation.transcription_metrics import Note, compute_note_metrics

    ref_notes = []
    if clip.reference_midi:
        from evaluation.benchmark import _midi_to_notes
        ref_bytes = Path(clip.reference_midi).read_bytes()
        ref_notes = _midi_to_notes(ref_bytes)

    pred_notes = [Note.from_dict(n) for n in output.get("notes", [])]
    ref_note_objs = [Note.from_dict(n) for n in ref_notes]

    return compute_note_metrics(pred_notes, ref_note_objs).to_dict()


def _compute_beat_metrics(output: dict[str, Any], clip: EvalClip) -> dict[str, Any]:
    """Compute beat tracking metrics against reference."""
    from evaluation.beat_metrics import compute_beat_metrics

    predicted_bpm = output.get("bpm")
    predicted_beats = output.get("beats", [])
    predicted_downbeats = output.get("downbeats")

    ref_beats = clip.reference.beats if clip.reference.beats else None
    ref_bpm = clip.reference.bpm
    ref_downbeats = clip.reference.downbeats if clip.reference.downbeats else None

    if ref_beats is None and ref_bpm is None:
        return {}

    return compute_beat_metrics(
        predicted_beats=predicted_beats,
        predicted_bpm=float(predicted_bpm) if predicted_bpm else 0.0,
        predicted_downbeats=predicted_downbeats,
        reference_beats=ref_beats,
        reference_bpm=ref_bpm,
        reference_downbeats=ref_downbeats,
    ).to_dict()


def _compute_harmony_metrics(output: dict[str, Any], clip: EvalClip) -> dict[str, Any]:
    """Compute harmony analysis metrics against reference."""
    from evaluation.analysis_metrics import compute_analysis_metrics

    predicted_key = output.get("key")
    predicted_bpm = output.get("tempo", {}).get("bpm") if output.get("tempo") else None
    predicted_meter = (
        f"{output['time_signature']['numerator']}/{output['time_signature']['denominator']}"
        if output.get("time_signature") else None
    )
    predicted_sections = [
        {"start": s["position"], "end": s["position"], "label": s.get("type", s.get("kind", ""))}
        for s in output.get("cadences", [])
    ]
    predicted_chords = [
        {"root": c["root"], "quality": c["quality"], "start": c["start"], "end": c["end"]}
        for c in output.get("chords", [])
    ]

    return compute_analysis_metrics(
        predicted_key=predicted_key,
        predicted_bpm=float(predicted_bpm) if predicted_bpm else 0.0,
        predicted_meter=predicted_meter,
        predicted_sections=predicted_sections,
        predicted_chords=predicted_chords,
        reference=clip.reference,
    ).to_dict()


def _compute_structure_metrics(output: dict[str, Any], clip: EvalClip) -> dict[str, Any]:
    """Compute structure analysis metrics against reference."""
    # Structure metrics placeholder - would need reference sections
    return {"sections_count": len(output.get("segments", []))}


def _aggregate_results(
    adapter: EngineAdapter,
    clip_results: list[EngineEvalResult],
    category: EngineCategory,
) -> EngineAggregateReport:
    """Aggregate clip-level results into engine-level report."""
    succeeded = [r for r in clip_results if r.success]
    failed = [r for r in clip_results if not r.success]

    avg_runtime = sum(r.runtime_s for r in succeeded) / len(succeeded) if succeeded else 0.0
    avg_memory = sum(r.peak_memory_mb for r in succeeded) / len(succeeded) if succeeded else 0.0

    # Category-specific aggregate metrics
    aggregate_metrics = _compute_category_aggregate(succeeded, category)

    return EngineAggregateReport(
        engine_name=adapter.engine_info.name,
        category=category,
        engine_info=adapter.engine_info,
        clips_total=len(clip_results),
        clips_succeeded=len(succeeded),
        clips_failed=len(failed),
        avg_runtime_s=avg_runtime,
        avg_peak_memory_mb=avg_memory,
        aggregate_metrics=aggregate_metrics,
        failure_cases=[
            {"clip_id": r.clip_id, "error": r.error}
            for r in failed
        ],
    )


def _compute_category_aggregate(
    succeeded: list[EngineEvalResult],
    category: EngineCategory,
) -> dict[str, Any]:
    """Compute category-specific aggregate metrics."""
    if not succeeded:
        return {}

    if category == "transcription":
        f1s = [r.metrics.get("note_f1", 0) for r in succeeded if r.metrics]
        return {
            "macro_note_f1": sum(f1s) / len(f1s) if f1s else 0,
            "macro_precision": sum(r.metrics.get("precision", 0) for r in succeeded if r.metrics) / len(succeeded) if succeeded else 0,
            "macro_recall": sum(r.metrics.get("recall", 0) for r in succeeded if r.metrics) / len(succeeded) if succeeded else 0,
        }
    elif category == "beat_tracking":
        f_measures = [r.metrics.get("f_measure", 0) for r in succeeded if r.metrics]
        return {
            "macro_f_measure": sum(f_measures) / len(f_measures) if f_measures else 0,
        }
    elif category == "harmony":
        key_accs = [r.metrics.get("key_accuracy", 0) for r in succeeded if r.metrics]
        chord_f1s = [r.metrics.get("chord_f1", 0) for r in succeeded if r.metrics]
        return {
            "macro_key_accuracy": sum(key_accs) / len(key_accs) if key_accs else 0,
            "macro_chord_f1": sum(chord_f1s) / len(chord_f1s) if chord_f1s else 0,
        }
    elif category == "structure":
        return {"avg_segments": sum(r.metrics.get("sections_count", 0) for r in succeeded if r.metrics) / len(succeeded) if succeeded else 0}

    return {}


def write_evaluation_report(
    reports: list[EngineAggregateReport],
    output_path: str,
) -> None:
    """Write a comparative evaluation report."""
    import json

    data = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "engines": [r.__dict__ for r in reports],
    }

    with open(output_path, "w") as f:
        json.dump(data, f, indent=2, default=str)

    # Also write markdown summary
    md_path = output_path.replace(".json", ".md")
    with open(md_path, "w") as f:
        f.write("# OSS Engine Evaluation Report\n\n")
        f.write(f"Generated: {data['generated_at']}\n\n")

        for r in reports:
            f.write(f"## {r.engine_name} ({r.category})\n\n")
            f.write(f"- **License**: {r.engine_info.license}\n")
            f.write(f"- **Model size**: {r.engine_info.model_size_mb or 'N/A'} MB\n")
            f.write(f"- **Requires GPU**: {r.engine_info.requires_gpu}\n")
            f.write(f"- **Clips**: {r.clips_succeeded}/{r.clips_total} succeeded\n")
            f.write(f"- **Avg runtime**: {r.avg_runtime_s:.2f}s\n")
            f.write(f"- **Avg memory**: {r.avg_peak_memory_mb:.1f} MB\n")
            f.write(f"- **Aggregate metrics**: {r.aggregate_metrics}\n")
            if r.failure_cases:
                f.write(f"- **Failures**: {len(r.failure_cases)} clips\n")
            f.write("\n")