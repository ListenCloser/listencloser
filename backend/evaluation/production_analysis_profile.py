"""Decompose production-profile music analysis latency on canonical audio.

This is an evaluation-only profiler. It reproduces the inputs to
``analyze.analyze_midi`` using the production harmony/melody engines, then wraps
major subcomponents so a single unchanged analysis call reports where time is
spent. Product output is not modified.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import tempfile
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Callable

import analyze
import music_features


def _seconds(call: Callable[[], Any]) -> tuple[float, Any]:
    started = time.perf_counter()
    value = call()
    return time.perf_counter() - started, value


class _TimedEngine:
    def __init__(self, engine: Any, name: str, timings: dict[str, list[float]]) -> None:
        self._engine = engine
        self._name = name
        self._timings = timings

    def __getattr__(self, name: str) -> Any:
        return getattr(self._engine, name)

    def analyze(self, *args: Any, **kwargs: Any) -> Any:
        started = time.perf_counter()
        try:
            return self._engine.analyze(*args, **kwargs)
        finally:
            self._timings[self._name].append(time.perf_counter() - started)


def _summary(values: list[float]) -> dict[str, Any]:
    return {
        "calls": len(values),
        "total_seconds": round(sum(values), 6),
        "trials_seconds": [round(value, 6) for value in values],
    }


def profile(input_path: Path, fmt: str) -> dict[str, Any]:
    raw_audio = input_path.read_bytes()

    transcribe_s, transcription = _seconds(
        lambda: music_features.transcribe_audio(raw_audio, fmt=fmt)
    )
    midi_bytes: bytes = transcription["midi"]
    decode_s, wav_bytes = _seconds(lambda: music_features.decode_audio_to_wav(raw_audio, fmt=fmt))
    beat_s, beat_result = _seconds(
        lambda: music_features.estimate_beats_with_engine(wav_bytes, engine_name="beat_this")
    )
    pulse = {
        "bpm": beat_result.get("bpm"),
        "beats": beat_result.get("beats") or [],
        "downbeats": beat_result.get("downbeats"),
        "provenance": beat_result.get("provenance"),
    }

    # Match production worker engine selection explicitly; Real-stack currently
    # lacks this env and therefore defaults to music21 instead of lv-chordia.
    os.environ["HARMONY_ENGINE"] = "lv_chordia"
    os.environ["MELODY_ENGINE"] = "lstom"

    timings: dict[str, list[float]] = defaultdict(list)

    original_harmony_factory = analyze.get_harmony_engine
    original_melody_factory = analyze.get_melody_engine
    original_rhythm = analyze._midi_rhythm

    import engines.melody.interpretation as melody_interpretation
    import engines.melody.motif_discovery as motif_discovery
    import engines.registry as registry
    import music21.converter as m21_converter

    original_theory_factory = registry.get_theory_engine
    original_m21_parse = m21_converter.parse
    original_interpret = melody_interpretation.interpret_melody
    original_discover = motif_discovery.discover_motifs

    def timed_harmony_factory(*args: Any, **kwargs: Any) -> Any:
        return _TimedEngine(original_harmony_factory(*args, **kwargs), "harmony_engine", timings)

    def timed_melody_factory(*args: Any, **kwargs: Any) -> Any:
        return _TimedEngine(original_melody_factory(*args, **kwargs), "melody_engine", timings)

    def timed_theory_factory(*args: Any, **kwargs: Any) -> Any:
        return _TimedEngine(original_theory_factory(*args, **kwargs), "theory_engine", timings)

    def timed_rhythm(*args: Any, **kwargs: Any) -> Any:
        started = time.perf_counter()
        try:
            return original_rhythm(*args, **kwargs)
        finally:
            timings["rhythm"].append(time.perf_counter() - started)

    def timed_m21_parse(*args: Any, **kwargs: Any) -> Any:
        started = time.perf_counter()
        try:
            return original_m21_parse(*args, **kwargs)
        finally:
            timings["independent_key_parse"].append(time.perf_counter() - started)

    def timed_interpret(*args: Any, **kwargs: Any) -> Any:
        started = time.perf_counter()
        try:
            return original_interpret(*args, **kwargs)
        finally:
            timings["melody_interpretation"].append(time.perf_counter() - started)

    def timed_discover(*args: Any, **kwargs: Any) -> Any:
        started = time.perf_counter()
        try:
            return original_discover(*args, **kwargs)
        finally:
            timings["motif_discovery"].append(time.perf_counter() - started)

    analyze.get_harmony_engine = timed_harmony_factory
    analyze.get_melody_engine = timed_melody_factory
    analyze._midi_rhythm = timed_rhythm
    registry.get_theory_engine = timed_theory_factory
    m21_converter.parse = timed_m21_parse
    melody_interpretation.interpret_melody = timed_interpret
    motif_discovery.discover_motifs = timed_discover

    midi_path: str | None = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".mid", delete=False) as handle:
            handle.write(midi_bytes)
            handle.flush()
            midi_path = handle.name

        analysis_s, result = _seconds(
            lambda: analyze.analyze_midi(midi_path, pulse=pulse, audio_bytes=wav_bytes)
        )
    finally:
        analyze.get_harmony_engine = original_harmony_factory
        analyze.get_melody_engine = original_melody_factory
        analyze._midi_rhythm = original_rhythm
        registry.get_theory_engine = original_theory_factory
        m21_converter.parse = original_m21_parse
        melody_interpretation.interpret_melody = original_interpret
        motif_discovery.discover_motifs = original_discover
        if midi_path:
            Path(midi_path).unlink(missing_ok=True)

    measured_total = sum(sum(values) for values in timings.values())
    residual = max(0.0, analysis_s - measured_total)
    melody = result.get("melody") or {}
    rhythm = result.get("rhythm") or {}

    return {
        "schema_version": 1,
        "scenario": "production_analysis_component_profile",
        "thresholds_enforced": False,
        "release_sha": os.environ.get("GITHUB_SHA"),
        "fixture": input_path.name,
        "fixture_sha256": hashlib.sha256(raw_audio).hexdigest(),
        "decoded_wav_sha256": hashlib.sha256(wav_bytes).hexdigest(),
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "harmony_engine": os.environ["HARMONY_ENGINE"],
            "melody_engine": os.environ["MELODY_ENGINE"],
            "beat_engine": "beat_this",
        },
        "preparation": {
            "transcribe_seconds": round(transcribe_s, 6),
            "decode_seconds": round(decode_s, 6),
            "beat_tracking_seconds": round(beat_s, 6),
        },
        "analysis_total_seconds": round(analysis_s, 6),
        "components": {name: _summary(values) for name, values in sorted(timings.items())},
        "unattributed_residual_seconds": round(residual, 6),
        "output_signature": {
            "key": result.get("key"),
            "chord_count": len(result.get("chords") or []),
            "roman_numeral_count": len(result.get("roman_numerals_theory") or []),
            "melody_note_count": len(melody.get("notes") or []),
            "rhythm_beat_count": rhythm.get("beat_count"),
            "pulse_beat_count": len(pulse["beats"]),
            "pulse_downbeat_count": len(pulse.get("downbeats") or []),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--format", default="m4a")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    result = profile(args.input, args.format)
    text = json.dumps(result, indent=2, sort_keys=True) + "\n"
    print(text, end="")
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
