"""Engine evaluation framework for OSS music model bakeoff.

This module provides a uniform interface for evaluating candidate OSS engines
against the existing evaluation infrastructure. It does NOT change production
routing — production code continues to use the existing engine seams.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any, Protocol, Literal

from evaluation.corpus import EvalClip
from evaluation.models import Reference


# Tolerance window for structure boundary matching (seconds).
# Follows MIREX structural segmentation convention: 0.5 second tolerance window
# with one-to-one boundary matching.
TOLERANCE_S = 0.5


EngineCategory = Literal[
    "transcription",
    "beat_tracking",
    "harmony",
    "structure",
]


class _BytesJSONEncoder(json.JSONEncoder):
    """JSON encoder that serializes bytes (e.g. MIDI payloads) losslessly.

    Bytes are encoded as ``{"__base64__": "<base64>"}`` so binary outputs
    round-trip through JSON safely and explicitly, instead of relying on
    ``str(bytes)`` reprs that required ``eval()`` to recover.
    """

    def default(self, o: Any) -> Any:
        if isinstance(o, bytes):
            import base64

            return {"__base64__": base64.b64encode(o).decode("ascii")}
        import numpy as np

        if isinstance(o, np.integer):
            return int(o)
        if isinstance(o, np.floating):
            return float(o)
        if isinstance(o, np.bool_):
            return bool(o)
        if isinstance(o, np.ndarray):
            return o.tolist()
        # Preserve prior default=str behavior for other non-serializable
        # objects (e.g. EngineInfo in the aggregate report).
        return str(o)


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
            json.dump(clip_result.__dict__, f, indent=2, cls=_BytesJSONEncoder)

    return _aggregate_results(adapter, clip_results, category)


def _check_clip_eligibility(category: EngineCategory, clip: EvalClip) -> str | None:
    """Check if a clip has required reference data for scoring.

    Returns None if eligible, or a reason string if ineligible.
    Ineligible clips are run for diagnostics but not scored.
    """
    if category == "transcription":
        if not clip.reference_midi:
            return "no reference MIDI for transcription scoring"
    elif category == "beat_tracking":
        if not clip.reference.beats and clip.reference.bpm is None:
            return "no reference beats or BPM for beat scoring"
    elif category == "harmony":
        if not clip.reference_midi:
            return "no reference MIDI for harmony scoring"
    elif category == "structure":
        if not clip.reference.sections:
            return "no reference sections for structure scoring"
    return None


def _run_clip_on_engine(
    adapter: EngineAdapter,
    clip: EvalClip,
    category: EngineCategory,
    warmup: bool = True,
    **adapter_kwargs,
) -> EngineEvalResult:
    """Run a single clip through the engine adapter.
    
    Timing: warm-up and prepare() are NOT included in measured runtime.
    Timing starts immediately before the actual inference run.
    """
    import os
    import time
    import tracemalloc
    from pathlib import Path

    # Pre-initialize for failure safety (values used if exception before measurement starts)
    elapsed = 0.0
    peak_mb = 0.0
    timer_started = False

    result = EngineEvalResult(
        engine_name=adapter.engine_info.name,
        clip_id=clip.id,
        category=category,
        success=False,
    )

    try:
        # --- Setup phase (NOT timed) ---
        if not adapter.is_available():
            raise RuntimeError(f"Engine {adapter.engine_info.name} not available")

        adapter.prepare()

        # Warm-up run (not timed) to avoid first-clip penalty for lazy loading/JIT
        if warmup:
            try:
                if category == "transcription":
                    audio_bytes = Path(clip.audio).read_bytes()
                    adapter.transcribe(audio_bytes, **adapter_kwargs)
                elif category == "beat_tracking":
                    audio_bytes = Path(clip.audio).read_bytes()
                    adapter.estimate_beats(audio_bytes, **adapter_kwargs)
                elif category == "harmony":
                    if clip.reference_midi:
                        midi_bytes = Path(clip.reference_midi).read_bytes()
                        adapter.analyze_harmony(midi_bytes, **adapter_kwargs)
                elif category == "structure":
                    audio_bytes = Path(clip.audio).read_bytes()
                    adapter.analyze_structure(audio_bytes, **adapter_kwargs)
            except Exception:
                # Warm-up failures are non-fatal
                pass

        # Check eligibility for scoring
        eligibility_reason = _check_clip_eligibility(category, clip)

        # --- Measured inference run ---
        tracemalloc.start()
        t0 = time.monotonic()
        timer_started = True

        if category == "transcription":
            audio_bytes = Path(clip.audio).read_bytes()
            output = adapter.transcribe(audio_bytes, **adapter_kwargs)
            if eligibility_reason:
                metrics = {}
                diagnostics = {"eligibility": "ineligible", "reason": eligibility_reason}
            else:
                metrics = _compute_transcription_metrics(output, clip)
                diagnostics = {}

        elif category == "beat_tracking":
            audio_bytes = Path(clip.audio).read_bytes()
            output = adapter.estimate_beats(audio_bytes, **adapter_kwargs)
            if eligibility_reason:
                metrics = {}
                diagnostics = {"eligibility": "ineligible", "reason": eligibility_reason}
            else:
                metrics = _compute_beat_metrics(output, clip)
                diagnostics = {}

        elif category == "harmony":
            if not clip.reference_midi:
                raise RuntimeError("Harmony evaluation requires reference MIDI")
            midi_bytes = Path(clip.reference_midi).read_bytes()
            output = adapter.analyze_harmony(midi_bytes, **adapter_kwargs)
            if eligibility_reason:
                metrics = {}
                diagnostics = {"eligibility": "ineligible", "reason": eligibility_reason}
            else:
                metrics = _compute_harmony_metrics(output, clip)
                diagnostics = {}

        elif category == "structure":
            audio_bytes = Path(clip.audio).read_bytes()
            output = adapter.analyze_structure(audio_bytes, **adapter_kwargs)
            if eligibility_reason:
                metrics = {}
                diagnostics = {"eligibility": "ineligible", "reason": eligibility_reason}
            else:
                metrics = _compute_structure_metrics(output, clip)
                diagnostics = {}

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
            diagnostics=diagnostics,
        )

    except Exception as e:
        if timer_started:
            elapsed = time.monotonic() - t0
            current, peak = tracemalloc.get_traced_memory()
            tracemalloc.stop()
            peak_mb = peak / (1024 * 1024)
        else:
            # Failure during setup (is_available/prepare/warmup) - no inference time
            elapsed = 0.0
            peak_mb = 0.0
        result = EngineEvalResult(
            engine_name=adapter.engine_info.name,
            clip_id=clip.id,
            category=category,
            success=False,
            error=str(e),
            runtime_s=elapsed,
            peak_memory_mb=peak_mb,
        )

    return result


def _compute_transcription_metrics(output: dict[str, Any], clip: EvalClip) -> dict[str, Any]:
    """Compute transcription metrics against reference."""
    if not clip.reference_midi:
        return {}

    from pathlib import Path
    from evaluation.transcription_metrics import Note, compute_note_metrics

    ref_notes = []
    if clip.reference_midi:
        from evaluation.benchmark import _midi_to_notes
        ref_bytes = Path(clip.reference_midi).read_bytes()
        ref_notes = _midi_to_notes(ref_bytes)

    pred_notes = [Note.from_dict(n) for n in output.get("notes", [])]

    return compute_note_metrics(pred_notes, ref_notes).to_dict()


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
    """Compute structure analysis metrics against reference segments.

    Uses tolerance-based one-to-one boundary matching (following MIREX convention).
    A predicted boundary matches a reference boundary if within tolerance window.
    """
    # Tolerance window in seconds (following MIREX structural segmentation convention)
    TOLERANCE_S = 0.5

    ref_sections = clip.reference.sections if clip.reference.sections else []
    pred_segments = output.get("segments", [])

    if not ref_sections or not pred_segments:
        return {"sections_count": len(pred_segments), "boundary_f1": 0.0, "boundary_precision": 0.0, "boundary_recall": 0.0, "tolerance_s": TOLERANCE_S}

    # Extract all boundaries (start and end times)
    ref_boundaries: list[float] = []
    for s in ref_sections:
        if "start" in s:
            ref_boundaries.append(float(s["start"]))
        if "end" in s:
            ref_boundaries.append(float(s["end"]))

    pred_boundaries: list[float] = []
    for s in pred_segments:
        if "start" in s:
            pred_boundaries.append(float(s["start"]))
        if "end" in s:
            pred_boundaries.append(float(s["end"]))

    if not ref_boundaries:
        return {"sections_count": len(pred_segments), "boundary_f1": 0.0, "boundary_precision": 0.0, "boundary_recall": 0.0, "tolerance_s": TOLERANCE_S}

    # One-to-one matching with tolerance: greedy nearest neighbor
    ref_matched = [False] * len(ref_boundaries)
    pred_matched = [False] * len(pred_boundaries)
    tp = 0

    # Sort both lists for greedy matching
    ref_sorted = sorted((b, i) for i, b in enumerate(ref_boundaries))
    pred_sorted = sorted((b, i) for i, b in enumerate(pred_boundaries))

    ri = 0
    pi = 0
    while ri < len(ref_sorted) and pi < len(pred_sorted):
        ref_b, ref_idx = ref_sorted[ri]
        pred_b, pred_idx = pred_sorted[pi]
        diff = abs(ref_b - pred_b)

        if diff <= TOLERANCE_S:
            # Match found
            tp += 1
            ref_matched[ref_idx] = True
            pred_matched[pred_idx] = True
            ri += 1
            pi += 1
        elif pred_b < ref_b - TOLERANCE_S:
            # Prediction too early, move to next prediction
            pi += 1
        else:
            # Reference too early, move to next reference
            ri += 1

    fp = len(pred_boundaries) - tp
    fn = len(ref_boundaries) - tp

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

    return {
        "sections_count": len(pred_segments),
        "boundary_precision": round(precision, 3),
        "boundary_recall": round(recall, 3),
        "boundary_f1": round(f1, 3),
        "tolerance_s": TOLERANCE_S,
        "num_ref_boundaries": len(ref_boundaries),
        "num_pred_boundaries": len(pred_boundaries),
    }


def _aggregate_results(
    adapter: EngineAdapter,
    clip_results: list[EngineEvalResult],
    category: EngineCategory,
) -> EngineAggregateReport:
    """Aggregate clip-level results into engine-level report."""
    succeeded = [r for r in clip_results if r.success]
    failed = [r for r in clip_results if not r.success]
    scored = [r for r in succeeded if not r.diagnostics.get("eligibility", "").startswith("ineligible")]
    ineligible = [r for r in succeeded if r.diagnostics.get("eligibility", "").startswith("ineligible")]

    # Runtime/memory: average over every clip where inference actually ran
    # (succeeded), including ineligible ones — an ineligible clip still
    # consumed inference time. Scored subset is used only for metrics.
    avg_runtime = sum(r.runtime_s for r in succeeded) / len(succeeded) if succeeded else 0.0
    avg_memory = sum(r.peak_memory_mb for r in succeeded) / len(succeeded) if succeeded else 0.0

    # Category-specific aggregate metrics (only from scored clips)
    aggregate_metrics = _compute_category_aggregate(scored, category)
    aggregate_metrics["clips_scored"] = len(scored)
    aggregate_metrics["clips_ineligible"] = len(ineligible)

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
        f1s = [v for v in (r.metrics.get("note_f1") for r in succeeded if r.metrics) if v is not None]
        precisions = [v for v in (r.metrics.get("note_precision") for r in succeeded if r.metrics) if v is not None]
        recalls = [v for v in (r.metrics.get("note_recall") for r in succeeded if r.metrics) if v is not None]
        return {
            "macro_note_f1": sum(f1s) / len(f1s) if f1s else 0,
            "macro_precision": sum(precisions) / len(precisions) if precisions else 0,
            "macro_recall": sum(recalls) / len(recalls) if recalls else 0,
        }
    elif category == "beat_tracking":
        f_measures = [v for v in (r.metrics.get("beat_f1") for r in succeeded if r.metrics) if v is not None]
        return {
            "macro_f_measure": sum(f_measures) / len(f_measures) if f_measures else 0,
        }
    elif category == "harmony":
        key_accs = [v for v in (r.metrics.get("key_correct") for r in succeeded if r.metrics) if v is not None]
        chord_f1s = [v for v in (r.metrics.get("chord_f1") for r in succeeded if r.metrics) if v is not None]
        return {
            "macro_key_accuracy": sum(key_accs) / len(key_accs) if key_accs else 0,
            "macro_chord_f1": sum(chord_f1s) / len(chord_f1s) if chord_f1s else 0,
        }
    elif category == "structure":
        boundary_f1s = [v for v in (r.metrics.get("boundary_f1") for r in succeeded if r.metrics) if v is not None]
        section_counts = [v for v in (r.metrics.get("sections_count") for r in succeeded if r.metrics) if v is not None]
        return {
            "macro_boundary_f1": sum(boundary_f1s) / len(boundary_f1s) if boundary_f1s else 0,
            "avg_segments": sum(section_counts) / len(section_counts) if section_counts else 0,
        }

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
        json.dump(data, f, indent=2, cls=_BytesJSONEncoder)

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
            ineligible = r.aggregate_metrics.get("clips_ineligible", 0)
            scored = r.aggregate_metrics.get("clips_scored", 0)
            f.write(
                f"- **Eligibility**: {scored} scored, {ineligible} ineligible, "
                f"{r.clips_failed} failed (of {r.clips_total} total)\n"
            )
            f.write(f"- **Avg runtime**: {r.avg_runtime_s:.2f}s\n")
            f.write(f"- **Avg memory**: {r.avg_peak_memory_mb:.1f} MB\n")
            f.write(f"- **Aggregate metrics**: {r.aggregate_metrics}\n")
            if r.failure_cases:
                f.write(f"- **Failures**: {len(r.failure_cases)} clips\n")
            f.write("\n")