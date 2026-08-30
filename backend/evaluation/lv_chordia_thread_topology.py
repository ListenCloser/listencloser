"""Measure lv-chordia CPU inference thread topology without changing output.

The released production engine runs five ChordNet ensemble members sequentially.
This evaluation holds the same five released models only for the duration of one
benchmark process, computes one production-shaped CQT, then compares CPU thread
topologies for the ensemble-inference portion. It does not change product code.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.resources
import json
import os
import platform
import statistics
import tempfile
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from importlib.metadata import version
from pathlib import Path
from typing import Any

import numpy as np
import torch
from lv_chordia.chord_recognition import MODEL_NAMES
from lv_chordia.chordnet_ismir_naive import ChordNet
from lv_chordia.extractors.cqt import CQTV2
from lv_chordia.extractors.xhmm_ismir import XHMMDecoder
from lv_chordia.mir import DataEntry, io
from lv_chordia.mir.nn.train import NetworkInterface
from lv_chordia.settings import DEFAULT_HOP_LENGTH, DEFAULT_SR

import music_features


@dataclass(frozen=True)
class Topology:
    name: str
    intraop_threads: int
    model_workers: int


def _timed(call: Callable[[], Any]) -> tuple[float, Any]:
    started = time.perf_counter()
    value = call()
    return time.perf_counter() - started, value


def _summary(values: list[float]) -> dict[str, Any]:
    return {
        "trials_seconds": [round(value, 6) for value in values],
        "median_seconds": round(statistics.median(values), 6),
        "min_seconds": round(min(values), 6),
        "max_seconds": round(max(values), 6),
    }


def _load_ensemble() -> list[NetworkInterface]:
    return [
        NetworkInterface(ChordNet(None), model_name, load_checkpoint=False)
        for model_name in MODEL_NAMES
    ]


def _prepare_cqt(audio_path: Path) -> np.ndarray:
    entry = DataEntry()
    entry.prop.set("sr", DEFAULT_SR)
    entry.prop.set("hop_length", DEFAULT_HOP_LENGTH)
    entry.append_file(str(audio_path), io.MusicIO, "music")
    entry.append_extractor(CQTV2, "cqt")
    return np.asarray(entry.cqt)


def _run_ensemble(
    ensemble: list[NetworkInterface],
    cqt: np.ndarray,
    model_workers: int,
) -> list[Any]:
    if model_workers == 1:
        return [net.inference(cqt) for net in ensemble]

    with ThreadPoolExecutor(max_workers=model_workers) as executor:
        return list(executor.map(lambda net: net.inference(cqt), ensemble))


def _fuse_probabilities(probabilities: list[Any]) -> list[np.ndarray]:
    return [
        np.mean([probability[index] for probability in probabilities], axis=0)
        for index in range(len(probabilities[0]))
    ]


def _decode(
    audio_path: Path,
    mean_probabilities: list[np.ndarray],
    chord_dict_name: str = "submission",
) -> list[dict[str, Any]]:
    resource = importlib.resources.files("lv_chordia.data").joinpath(
        f"{chord_dict_name}_chord_list.txt"
    )
    with importlib.resources.as_file(resource) as data_file:
        hmm = XHMMDecoder(template_file=str(data_file))

    entry = DataEntry()
    entry.prop.set("sr", DEFAULT_SR)
    entry.prop.set("hop_length", DEFAULT_HOP_LENGTH)
    entry.append_file(str(audio_path), io.MusicIO, "music")
    chordlab = hmm.decode_to_chordlab(entry, mean_probabilities, False)
    return [
        {
            "start_time": float(f"{segment[0]:.2f}"),
            "end_time": float(f"{segment[1]:.2f}"),
            "chord": str(segment[2]),
        }
        for segment in chordlab
    ]


def _output_sha256(output: list[dict[str, Any]]) -> str:
    payload = json.dumps(output, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()


def _max_probability_delta(
    reference: list[np.ndarray],
    candidate: list[np.ndarray],
) -> float:
    return max(
        float(np.max(np.abs(reference_item - candidate_item)))
        for reference_item, candidate_item in zip(reference, candidate, strict=True)
    )


def _candidate_topologies(default_threads: int, cpu_count: int) -> list[Topology]:
    topologies = [Topology("sequential_default", default_threads, 1)]
    seen = {(default_threads, 1)}

    for intraop_threads in (1, 2, 4):
        if intraop_threads <= cpu_count and (intraop_threads, 1) not in seen:
            topologies.append(Topology(f"sequential_intra_{intraop_threads}", intraop_threads, 1))
            seen.add((intraop_threads, 1))

    for model_workers in (2, 4, 5):
        key = (default_threads, model_workers)
        if key not in seen:
            topologies.append(
                Topology(
                    f"parallel_{model_workers}_intra_default",
                    default_threads,
                    model_workers,
                )
            )
            seen.add(key)

    for model_workers, intraop_threads in ((2, 1), (4, 1), (5, 1), (2, 2)):
        key = (intraop_threads, model_workers)
        if intraop_threads <= cpu_count and key not in seen:
            topologies.append(
                Topology(
                    f"parallel_{model_workers}_intra_{intraop_threads}",
                    intraop_threads,
                    model_workers,
                )
            )
            seen.add(key)

    return topologies


def benchmark(input_path: Path, fmt: str, trials: int) -> dict[str, Any]:
    if trials < 2:
        raise ValueError("trials must be >= 2")

    raw_audio = input_path.read_bytes()
    default_threads = torch.get_num_threads()
    interop_threads = torch.get_num_interop_threads()
    cpu_count = os.cpu_count() or 1

    decoded_wav = music_features.decode_audio_to_wav(raw_audio, fmt=fmt)
    with tempfile.NamedTemporaryFile(suffix=".wav") as audio_file:
        audio_file.write(decoded_wav)
        audio_file.flush()
        audio_path = Path(audio_file.name)

        load_seconds, ensemble = _timed(_load_ensemble)
        cqt_seconds, cqt = _timed(lambda: _prepare_cqt(audio_path))

        # Warm framework/kernel state once before comparing thread topologies.
        torch.set_num_threads(default_threads)
        _run_ensemble(ensemble, cqt, 1)

        topology_results: list[dict[str, Any]] = []
        reference_output: list[dict[str, Any]] | None = None
        reference_probs: list[np.ndarray] | None = None
        baseline_median: float | None = None

        for topology in _candidate_topologies(default_threads, cpu_count):
            torch.set_num_threads(topology.intraop_threads)

            # Warm each topology after resizing the global intra-op pool.
            _run_ensemble(ensemble, cqt, topology.model_workers)

            durations: list[float] = []
            outputs_equivalent: list[bool] = []
            probability_deltas: list[float] = []
            output_sha: str | None = None

            for _ in range(trials):
                started = time.perf_counter()
                probabilities = _run_ensemble(ensemble, cqt, topology.model_workers)
                duration = time.perf_counter() - started
                mean_probabilities = _fuse_probabilities(probabilities)
                output = _decode(audio_path, mean_probabilities)
                durations.append(duration)

                if reference_output is None:
                    reference_output = output
                    reference_probs = mean_probabilities

                assert reference_probs is not None
                equivalent = output == reference_output
                outputs_equivalent.append(equivalent)
                probability_deltas.append(
                    _max_probability_delta(reference_probs, mean_probabilities)
                )
                output_sha = _output_sha256(output)

            summary = _summary(durations)
            median_seconds = float(summary["median_seconds"])
            if baseline_median is None:
                baseline_median = median_seconds

            topology_results.append(
                {
                    "name": topology.name,
                    "intraop_threads": topology.intraop_threads,
                    "model_workers": topology.model_workers,
                    **summary,
                    "speedup_vs_sequential_default": round(
                        baseline_median / median_seconds,
                        4,
                    ),
                    "all_outputs_equivalent": all(outputs_equivalent),
                    "max_abs_probability_delta": round(max(probability_deltas), 10),
                    "output_sha256": output_sha,
                }
            )

        torch.set_num_threads(default_threads)

    assert reference_output is not None
    all_equivalent = all(result["all_outputs_equivalent"] for result in topology_results)

    return {
        "schema_version": 1,
        "scenario": "lv_chordia_cpu_thread_topology",
        "thresholds_enforced": False,
        "fixture": input_path.name,
        "fixture_sha256": hashlib.sha256(raw_audio).hexdigest(),
        "decoded_wav_sha256": hashlib.sha256(decoded_wav).hexdigest(),
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "cpu_count": cpu_count,
            "torch": torch.__version__,
            "lv_chordia": version("lv-chordia"),
            "default_intraop_threads": default_threads,
            "interop_threads": interop_threads,
        },
        "preparation": {
            "ensemble_load_seconds": round(load_seconds, 6),
            "cqt_seconds": round(cqt_seconds, 6),
        },
        "output_signature": {
            "segment_count": len(reference_output),
            "sha256": _output_sha256(reference_output),
        },
        "outputs_equivalent": all_equivalent,
        "topologies": topology_results,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--format", default="m4a")
    parser.add_argument("--trials", type=int, default=3)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    result = benchmark(args.input, fmt=args.format, trials=args.trials)
    text = json.dumps(result, indent=2, sort_keys=True) + "\n"
    print(text, end="")
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text)

    if not result["outputs_equivalent"]:
        raise SystemExit("thread topology changed lv-chordia chord output")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
