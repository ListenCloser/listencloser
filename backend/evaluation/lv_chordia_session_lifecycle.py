"""Measure released lv-chordia one-shot vs retained-ensemble lifecycle.

The production dependency is lv-chordia 1.1.0. Its one-shot
``chord_recognition()`` constructs and loads all five ``NetworkInterface``
instances on every call. Upstream later added ``LVChordiaSession`` on master,
but that API has not received a new PyPI release. This evaluation reproduces
the session architecture using only the installed 1.1.0 objects, without
changing the production dependency or product behavior.
"""

from __future__ import annotations

import argparse
import gc
import hashlib
import importlib.resources
import json
import statistics
import time
from pathlib import Path
from typing import Any

import numpy as np

from lv_chordia.chord_recognition import chord_recognition, MODEL_NAMES
from lv_chordia.chordnet_ismir_naive import ChordNet
from lv_chordia.extractors.cqt import CQTV2
from lv_chordia.extractors.xhmm_ismir import XHMMDecoder
from lv_chordia.mir import DataEntry, io
from lv_chordia.mir.nn.train import NetworkInterface
from lv_chordia.settings import DEFAULT_HOP_LENGTH, DEFAULT_SR


def _timed(callable_obj):
    started = time.perf_counter()
    value = callable_obj()
    return time.perf_counter() - started, value


def _rss_mebibytes() -> float | None:
    status = Path("/proc/self/status")
    if not status.exists():
        return None
    for line in status.read_text().splitlines():
        if line.startswith("VmRSS:"):
            kib = float(line.split()[1])
            return round(kib / 1024.0, 3)
    return None


def _output_sha256(output: list[dict[str, Any]]) -> str:
    payload = json.dumps(output, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()


def _load_ensemble() -> list[NetworkInterface]:
    return [
        NetworkInterface(ChordNet(None), model_name, load_checkpoint=False)
        for model_name in MODEL_NAMES
    ]


def _tensor_bytes(ensemble: list[NetworkInterface]) -> int:
    """Count unique live model/optimizer tensor storage retained by the ensemble."""
    import torch

    seen: set[tuple[str, int]] = set()
    total = 0

    def visit(value: Any) -> None:
        nonlocal total
        if torch.is_tensor(value):
            if value.device.type == "meta":
                return
            key = (str(value.device), value.data_ptr())
            if key not in seen:
                seen.add(key)
                total += value.numel() * value.element_size()
            return
        if isinstance(value, dict):
            for child in value.values():
                visit(child)
            return
        if isinstance(value, list | tuple):
            for child in value:
                visit(child)

    for interface in ensemble:
        visit(interface.net.state_dict())
        visit(interface.optimizer.state)
    return total


def _recognize_with_ensemble(
    ensemble: list[NetworkInterface],
    audio_path: Path,
    chord_dict_name: str = "submission",
) -> tuple[list[dict[str, Any]], dict[str, float]]:
    timings: dict[str, float] = {}

    started = time.perf_counter()
    resource = importlib.resources.files("lv_chordia.data").joinpath(
        f"{chord_dict_name}_chord_list.txt"
    )
    with importlib.resources.as_file(resource) as data_file:
        hmm = XHMMDecoder(template_file=str(data_file))
    timings["hmm_setup_seconds"] = time.perf_counter() - started

    entry = DataEntry()
    entry.prop.set("sr", DEFAULT_SR)
    entry.prop.set("hop_length", DEFAULT_HOP_LENGTH)
    entry.append_file(str(audio_path), io.MusicIO, "music")
    entry.append_extractor(CQTV2, "cqt")

    started = time.perf_counter()
    cqt = entry.cqt
    timings["cqt_seconds"] = time.perf_counter() - started

    probs = []
    started = time.perf_counter()
    for net in ensemble:
        probs.append(net.inference(cqt))
    timings["ensemble_inference_seconds"] = time.perf_counter() - started

    started = time.perf_counter()
    mean_probs = [np.mean([p[i] for p in probs], axis=0) for i in range(len(probs[0]))]
    chordlab = hmm.decode_to_chordlab(entry, mean_probs, False)
    timings["fusion_decode_seconds"] = time.perf_counter() - started

    output = [
        {
            "start_time": float(f"{segment[0]:.2f}"),
            "end_time": float(f"{segment[1]:.2f}"),
            "chord": str(segment[2]),
        }
        for segment in chordlab
    ]
    return output, {name: round(value, 6) for name, value in timings.items()}


def _summary(values: list[float]) -> dict[str, Any]:
    return {
        "trials_seconds": [round(value, 6) for value in values],
        "median_seconds": round(statistics.median(values), 6),
        "min_seconds": round(min(values), 6),
        "max_seconds": round(max(values), 6),
    }


def benchmark(input_path: Path, trials: int = 3) -> dict[str, Any]:
    if trials < 2:
        raise ValueError("trials must be >= 2")

    raw_audio = input_path.read_bytes()

    # Measure residency before any model checkpoint has been loaded in this
    # process. Running one-shot first would let PyTorch's allocator retain pages
    # and understate the cost of keeping the ensemble live.
    gc.collect()
    rss_before_load = _rss_mebibytes()
    retained_load_s, ensemble = _timed(_load_ensemble)
    rss_after_load = _rss_mebibytes()
    retained_tensor_bytes = _tensor_bytes(ensemble)

    retained_totals: list[float] = []
    retained_components: list[dict[str, float]] = []
    retained_outputs: list[list[dict[str, Any]]] = []
    for _ in range(trials):
        duration, payload = _timed(lambda: _recognize_with_ensemble(ensemble, input_path))
        output, components = payload
        retained_totals.append(duration)
        retained_components.append(components)
        retained_outputs.append(output)

    reference = retained_outputs[0]
    reference_sha = _output_sha256(reference)
    retained_equivalent = all(
        output == reference and _output_sha256(output) == reference_sha
        for output in retained_outputs
    )

    ensemble.clear()
    gc.collect()
    rss_after_release = _rss_mebibytes()

    # The software stack and kernels are now warm, but each measured one-shot
    # call still reconstructs and reloads the five-model ensemble exactly as
    # released lv-chordia 1.1.0 does in production.
    warm_one_shot_totals: list[float] = []
    warm_one_shot_equivalent: list[bool] = []
    for _ in range(trials):
        duration, output = _timed(lambda: chord_recognition(str(input_path)))
        warm_one_shot_totals.append(duration)
        warm_one_shot_equivalent.append(
            output == reference and _output_sha256(output) == reference_sha
        )

    retained_median = statistics.median(retained_totals)
    one_shot_median = statistics.median(warm_one_shot_totals)
    saved = one_shot_median - retained_median
    speedup = one_shot_median / retained_median if retained_median > 0 else None

    rss_delta = None
    if rss_before_load is not None and rss_after_load is not None:
        rss_delta = round(rss_after_load - rss_before_load, 3)

    return {
        "schema_version": 2,
        "scenario": "lv_chordia_retained_ensemble_lifecycle",
        "thresholds_enforced": False,
        "fixture": input_path.name,
        "fixture_sha256": hashlib.sha256(raw_audio).hexdigest(),
        "output_signature": {
            "segment_count": len(reference),
            "sha256": reference_sha,
        },
        "outputs_equivalent": retained_equivalent and all(warm_one_shot_equivalent),
        "retained_load_seconds": round(retained_load_s, 6),
        "resident_memory": {
            "before_load_mib": rss_before_load,
            "after_load_mib": rss_after_load,
            "delta_mib": rss_delta,
            "after_release_mib": rss_after_release,
            "live_tensor_mib": round(retained_tensor_bytes / (1024 * 1024), 3),
        },
        "retained_calls": {
            **_summary(retained_totals),
            "components": retained_components,
        },
        "warm_one_shot_calls": _summary(warm_one_shot_totals),
        "retained_vs_one_shot": {
            "median_seconds_saved_per_call": round(saved, 6),
            "median_speedup": round(speedup, 4) if speedup is not None else None,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--trials", type=int, default=3)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    result = benchmark(args.input, trials=args.trials)
    text = json.dumps(result, indent=2, sort_keys=True) + "\n"
    print(text, end="")
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text)

    if not result["outputs_equivalent"]:
        raise SystemExit("retained ensemble changed lv-chordia output")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
