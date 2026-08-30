"""Score every lv-chordia ensemble subset on pinned GuitarSet excerpts.

The production lv-chordia 1.1.0 path averages a five-model ensemble. After
lifecycle profiling showed that model retention does not materially reduce
steady-state latency, this evaluation asks the next question: whether any
smaller ensemble preserves chord quality while reducing actual model inference
work.

All 31 non-empty subsets are decoded from the same per-model probability
outputs, so each source clip pays for CQT and the five model passes only once.
No production routing, dependency, or model behavior is changed.
"""

from __future__ import annotations

import argparse
import importlib.resources
import itertools
import json
import statistics
import tempfile
import time
from pathlib import Path
from typing import Any

import numpy as np
from lv_chordia.chord_recognition import MODEL_NAMES, chord_recognition
from lv_chordia.chordnet_ismir_naive import ChordNet
from lv_chordia.extractors.cqt import CQTV2
from lv_chordia.extractors.xhmm_ismir import XHMMDecoder
from lv_chordia.mir import DataEntry, io
from lv_chordia.mir.nn.train import NetworkInterface
from lv_chordia.settings import DEFAULT_HOP_LENGTH, DEFAULT_SR

from evaluation.chord_eval import evaluate_chords
from evaluation.datasets.parsers import parse_guitarset_harmony
from evaluation.datasets.registry import resolve_clip
from evaluation.slicing import slice_audio, slice_chord_annotations

_METRIC_KEYS = ("root", "majmin", "mirex", "overseg", "underseg", "seg")
_QUALITY_TO_MIR = {
    "M": "maj",
    "m": "min",
    "dim": "dim",
    "aug": "aug",
    "7": "7",
    "maj7": "maj7",
    "min7": "min7",
    "sus2": "sus2",
    "sus4": "sus4",
}


def _load_manifest(name: str) -> dict[str, Any]:
    path = Path(__file__).resolve().parent / "corpora" / f"{name}.json"
    return json.loads(path.read_text())


def _guitarset_clips(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    return [clip for clip in manifest["clips"] if clip.get("dataset") == "guitarset"]


def _load_ensemble() -> list[NetworkInterface]:
    return [
        NetworkInterface(ChordNet(None), model_name, load_checkpoint=False)
        for model_name in MODEL_NAMES
    ]


def _hmm_decoder() -> XHMMDecoder:
    resource = importlib.resources.files("lv_chordia.data").joinpath(
        "submission_chord_list.txt"
    )
    with importlib.resources.as_file(resource) as path:
        return XHMMDecoder(template_file=str(path))


def _reference_arrays(
    chords: list[dict[str, Any]],
) -> tuple[np.ndarray, list[str]]:
    intervals: list[list[float]] = []
    labels: list[str] = []
    for chord in chords:
        root = str(chord.get("root") or "")
        quality = str(chord.get("quality") or "")
        if not root:
            continue
        mir_quality = _QUALITY_TO_MIR.get(quality, quality)
        label = f"{root}:{mir_quality}" if mir_quality else "X"
        start = float(chord["start"])
        end = float(chord["end"])
        if end <= start:
            continue
        intervals.append([start, end])
        labels.append(label)
    if not intervals:
        return np.zeros((0, 2), dtype=float), []
    return np.asarray(intervals, dtype=float), labels


def _prediction_output(chordlab: Any) -> list[dict[str, Any]]:
    return [
        {
            "start_time": float(f"{segment[0]:.2f}"),
            "end_time": float(f"{segment[1]:.2f}"),
            "chord": str(segment[2]),
        }
        for segment in chordlab
    ]


def _prediction_arrays(
    output: list[dict[str, Any]],
) -> tuple[np.ndarray, list[str]]:
    if not output:
        return np.zeros((0, 2), dtype=float), []
    return (
        np.asarray(
            [[item["start_time"], item["end_time"]] for item in output],
            dtype=float,
        ),
        [str(item["chord"]) for item in output],
    )


def _decode_subset(
    entry: DataEntry,
    hmm: XHMMDecoder,
    model_probabilities: list[Any],
    members: tuple[int, ...],
) -> tuple[list[dict[str, Any]], float]:
    started = time.perf_counter()
    selected = [model_probabilities[index] for index in members]
    mean_probabilities = [
        np.mean([probability[index] for probability in selected], axis=0)
        for index in range(len(selected[0]))
    ]
    chordlab = hmm.decode_to_chordlab(entry, mean_probabilities, False)
    duration = time.perf_counter() - started
    return _prediction_output(chordlab), duration


def _subset_id(members: tuple[int, ...]) -> str:
    return "+".join(f"s{member}" for member in members)


def _weighted_mean(values: list[float], weights: list[float]) -> float:
    return float(np.average(np.asarray(values), weights=np.asarray(weights)))


def _aggregate_candidate(
    candidate: dict[str, Any],
    full_candidate: dict[str, Any] | None = None,
) -> dict[str, Any]:
    clips = candidate["clips"]
    weights = [float(clip["reference_duration_seconds"]) for clip in clips]
    aggregate: dict[str, Any] = {
        "clip_count": len(clips),
        "members": candidate["members"],
        "member_count": len(candidate["members"]),
        "median_model_inference_seconds": round(
            statistics.median(float(clip["model_inference_seconds"]) for clip in clips),
            6,
        ),
        "mean_model_inference_seconds": round(
            statistics.mean(float(clip["model_inference_seconds"]) for clip in clips),
            6,
        ),
        "median_decode_seconds": round(
            statistics.median(float(clip["decode_seconds"]) for clip in clips),
            6,
        ),
    }
    for key in _METRIC_KEYS:
        values = [float(clip["metrics"][key]) for clip in clips]
        aggregate[f"{key}_macro"] = round(statistics.mean(values), 6)
        aggregate[f"{key}_duration_weighted"] = round(_weighted_mean(values, weights), 6)

    if full_candidate is not None:
        full = full_candidate["aggregate"]
        full_latency = float(full["median_model_inference_seconds"])
        latency = float(aggregate["median_model_inference_seconds"])
        aggregate["inference_speedup_vs_full"] = round(
            full_latency / latency if latency > 0 else 0.0,
            4,
        )
        for key in ("root", "majmin", "mirex"):
            metric = f"{key}_duration_weighted"
            aggregate[f"{metric}_delta_vs_full"] = round(
                float(aggregate[metric]) - float(full[metric]),
                6,
            )
    return aggregate


def _pareto_frontier(candidates: list[dict[str, Any]]) -> list[str]:
    """Return candidates not dominated on quality (higher) and latency (lower)."""

    def dominates(left: dict[str, Any], right: dict[str, Any]) -> bool:
        l = left["aggregate"]
        r = right["aggregate"]
        quality_keys = (
            "root_duration_weighted",
            "majmin_duration_weighted",
            "mirex_duration_weighted",
        )
        quality_not_worse = all(float(l[key]) >= float(r[key]) for key in quality_keys)
        latency_not_worse = float(l["median_model_inference_seconds"]) <= float(
            r["median_model_inference_seconds"]
        )
        strictly_better = any(float(l[key]) > float(r[key]) for key in quality_keys) or float(
            l["median_model_inference_seconds"]
        ) < float(r["median_model_inference_seconds"])
        return quality_not_worse and latency_not_worse and strictly_better

    return [
        candidate["id"]
        for candidate in candidates
        if not any(
            dominates(other, candidate)
            for other in candidates
            if other["id"] != candidate["id"]
        )
    ]


def evaluate(corpus: str = "real_audio_v1") -> dict[str, Any]:
    manifest = _load_manifest(corpus)
    clips = _guitarset_clips(manifest)
    if not clips:
        raise RuntimeError(f"no GuitarSet clips found in corpus {corpus!r}")

    ensemble = _load_ensemble()
    hmm = _hmm_decoder()
    subset_members = [
        members
        for count in range(1, len(ensemble) + 1)
        for members in itertools.combinations(range(len(ensemble)), count)
    ]
    candidates: dict[str, dict[str, Any]] = {
        _subset_id(members): {
            "id": _subset_id(members),
            "members": list(members),
            "clips": [],
        }
        for members in subset_members
    }
    model_timings_by_clip: dict[str, list[float]] = {}
    full_members = tuple(range(len(ensemble)))
    full_id = _subset_id(full_members)
    production_equivalence: dict[str, bool] = {}

    for clip in clips:
        resolved = resolve_clip(clip)
        if not resolved.annotations_path:
            raise RuntimeError(f"{clip['id']}: GuitarSet JAMS annotation missing")

        start = float(clip.get("excerpt_start", 0.0))
        end = float(clip.get("excerpt_end", 20.0))
        source_audio = Path(resolved.audio_path).read_bytes()
        excerpt_audio = slice_audio(source_audio, start, end)
        harmony = parse_guitarset_harmony(Path(resolved.annotations_path).read_text())
        reference_chords = slice_chord_annotations(harmony["chords"], start, end)
        ref_intervals, ref_labels = _reference_arrays(reference_chords)
        if len(ref_intervals) == 0:
            raise RuntimeError(f"{clip['id']}: no chord reference in excerpt")
        reference_duration = max(float(ref_intervals[-1][1] - ref_intervals[0][0]), 1e-6)

        with tempfile.NamedTemporaryFile(suffix=".wav") as audio_file:
            audio_file.write(excerpt_audio)
            audio_file.flush()

            entry = DataEntry()
            entry.prop.set("sr", DEFAULT_SR)
            entry.prop.set("hop_length", DEFAULT_HOP_LENGTH)
            entry.append_file(audio_file.name, io.MusicIO, "music")
            entry.append_extractor(CQTV2, "cqt")

            cqt_started = time.perf_counter()
            cqt = entry.cqt
            cqt_seconds = time.perf_counter() - cqt_started

            probabilities: list[Any] = []
            model_seconds: list[float] = []
            for model in ensemble:
                started = time.perf_counter()
                probabilities.append(model.inference(cqt))
                model_seconds.append(time.perf_counter() - started)
            model_timings_by_clip[clip["id"]] = [round(value, 6) for value in model_seconds]

            full_output: list[dict[str, Any]] | None = None
            for members in subset_members:
                candidate_id = _subset_id(members)
                output, decode_seconds = _decode_subset(entry, hmm, probabilities, members)
                pred_intervals, pred_labels = _prediction_arrays(output)
                metrics = evaluate_chords(
                    pred_intervals,
                    pred_labels,
                    ref_intervals,
                    ref_labels,
                )
                if "error" in metrics:
                    raise RuntimeError(
                        f"{clip['id']} {candidate_id}: chord scoring failed: {metrics['error']}"
                    )
                candidates[candidate_id]["clips"].append(
                    {
                        "clip_id": clip["id"],
                        "source_id": clip["source_id"],
                        "reference_chord_count": len(ref_labels),
                        "reference_duration_seconds": round(reference_duration, 6),
                        "cqt_seconds": round(cqt_seconds, 6),
                        "model_inference_seconds": round(
                            sum(model_seconds[index] for index in members),
                            6,
                        ),
                        "decode_seconds": round(decode_seconds, 6),
                        "predicted_chord_count": len(output),
                        "metrics": {key: round(float(metrics[key]), 6) for key in _METRIC_KEYS},
                    }
                )
                if members == full_members:
                    full_output = output

            if full_output is None:
                raise RuntimeError(f"{clip['id']}: full ensemble output missing")
            production_output = chord_recognition(audio_file.name)
            production_equivalence[clip["id"]] = production_output == full_output
            if not production_equivalence[clip["id"]]:
                raise RuntimeError(
                    f"{clip['id']}: reconstructed five-model ensemble differs from production"
                )

    candidate_list = list(candidates.values())
    full_candidate = candidates[full_id]
    full_candidate["aggregate"] = _aggregate_candidate(full_candidate)
    for candidate in candidate_list:
        if candidate["id"] == full_id:
            continue
        candidate["aggregate"] = _aggregate_candidate(candidate, full_candidate)
    full_candidate["aggregate"]["inference_speedup_vs_full"] = 1.0
    for key in ("root", "majmin", "mirex"):
        full_candidate["aggregate"][f"{key}_duration_weighted_delta_vs_full"] = 0.0

    candidate_list.sort(
        key=lambda candidate: (
            -float(candidate["aggregate"]["root_duration_weighted"]),
            -float(candidate["aggregate"]["majmin_duration_weighted"]),
            float(candidate["aggregate"]["median_model_inference_seconds"]),
        )
    )

    return {
        "schema_version": 1,
        "scenario": "lv_chordia_ensemble_quality_latency_pareto",
        "thresholds_enforced": False,
        "corpus": corpus,
        "dataset": "guitarset",
        "clip_count": len(clips),
        "clip_ids": [clip["id"] for clip in clips],
        "model_names": list(MODEL_NAMES),
        "candidate_count": len(candidate_list),
        "production_full_subset": full_id,
        "production_equivalent_on_all_clips": all(production_equivalence.values()),
        "production_equivalence": production_equivalence,
        "model_inference_seconds_by_clip": model_timings_by_clip,
        "pareto_frontier": _pareto_frontier(candidate_list),
        "candidates": candidate_list,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", default="real_audio_v1")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    result = evaluate(args.corpus)
    text = json.dumps(result, indent=2, sort_keys=True) + "\n"
    print(text, end="")
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
