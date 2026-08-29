"""Measure whether a separated bass stem improves production Basic Pitch AMT."""

from __future__ import annotations

import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from backend.evaluation.analysis_v3.multitrack_transcription.adapters.basic_pitch import (
    run_basic_pitch,
)
from backend.evaluation.analysis_v3.multitrack_transcription.metrics import (
    MatchMetrics,
    NoteEvent,
    match_notes,
)
import numpy as np
import soundfile as sf


@dataclass(frozen=True)
class BassAmtScore:
    onset: MatchMetrics
    onset_offset: MatchMetrics
    runtime_seconds: float | None
    process_max_rss_mb: float | None
    predicted_notes_reported: int | None
    provenance: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "onset": asdict(self.onset),
            "onset_offset": asdict(self.onset_offset),
            "runtime_seconds": self.runtime_seconds,
            "process_max_rss_mb": self.process_max_rss_mb,
            "predicted_notes_reported": self.predicted_notes_reported,
            "provenance": self.provenance,
        }


@dataclass(frozen=True)
class BassAmtComparison:
    mixture: BassAmtScore
    bass_stem: BassAmtScore

    @property
    def onset_f1_delta(self) -> float:
        return self.bass_stem.onset.f1 - self.mixture.onset.f1

    @property
    def onset_offset_f1_delta(self) -> float:
        return self.bass_stem.onset_offset.f1 - self.mixture.onset_offset.f1

    def to_dict(self) -> dict[str, Any]:
        return {
            "mixture": self.mixture.to_dict(),
            "bass_stem": self.bass_stem.to_dict(),
            "onset_f1_delta": round(self.onset_f1_delta, 4),
            "onset_offset_f1_delta": round(self.onset_offset_f1_delta, 4),
        }


def _mono_audio(audio: np.ndarray) -> np.ndarray:
    samples = np.asarray(audio, dtype=np.float32)
    if samples.ndim == 1:
        return samples
    if samples.ndim != 2:
        raise ValueError(f"Unsupported audio rank: {samples.ndim}")
    if samples.shape[0] <= 8 and samples.shape[0] < samples.shape[1]:
        return samples.mean(axis=0)
    if samples.shape[1] <= 8 and samples.shape[1] < samples.shape[0]:
        return samples.mean(axis=1)
    raise ValueError(f"Ambiguous audio channel layout: {samples.shape}")


def _load_note_events(paths: list[Path], *, end_seconds: float) -> list[NoteEvent]:
    if end_seconds <= 0:
        raise ValueError("end_seconds must be positive")

    import pretty_midi

    events: list[NoteEvent] = []
    for path in paths:
        if not path.is_file():
            raise ValueError(f"Missing MIDI: {path}")
        midi = pretty_midi.PrettyMIDI(str(path))
        for instrument in midi.instruments:
            if instrument.is_drum:
                continue
            for note in instrument.notes:
                start = float(note.start)
                end = float(note.end)
                if start < 0.0 or start >= end_seconds or end <= 0.0:
                    continue
                clipped_end = min(end, end_seconds)
                if clipped_end <= start:
                    continue
                events.append(
                    NoteEvent(
                        pitch=int(note.pitch),
                        start=start,
                        end=clipped_end,
                        program=int(instrument.program),
                        is_drum=False,
                    )
                )
    return events


def score_basic_pitch_audio(
    audio: np.ndarray,
    sample_rate: int,
    reference_midi_paths: list[Path],
    *,
    excerpt_seconds: float,
) -> BassAmtScore:
    """Run the production Basic Pitch engine and score canonical AMT metrics."""
    if not reference_midi_paths:
        raise ValueError("reference_midi_paths must be non-empty")
    if excerpt_seconds <= 0:
        raise ValueError("excerpt_seconds must be positive")

    reference = _load_note_events(reference_midi_paths, end_seconds=excerpt_seconds)
    if not reference:
        raise ValueError("No bass reference notes in selected excerpt")

    with tempfile.TemporaryDirectory(prefix="hello-ai-separation-bass-") as temp_dir:
        root = Path(temp_dir)
        audio_path = root / "input.wav"
        prediction_path = root / "prediction.mid"
        sf.write(
            audio_path,
            _mono_audio(audio),
            sample_rate,
            format="WAV",
            subtype="FLOAT",
        )
        measurement = run_basic_pitch(audio_path, prediction_path)
        predicted = _load_note_events([prediction_path], end_seconds=excerpt_seconds)

    return BassAmtScore(
        onset=match_notes(reference, predicted),
        onset_offset=match_notes(reference, predicted, require_offset=True),
        runtime_seconds=measurement.get("runtime_seconds"),
        process_max_rss_mb=measurement.get("process_max_rss_mb"),
        predicted_notes_reported=measurement.get("predicted_notes"),
        provenance=dict(measurement.get("provenance") or {}),
    )


def compare_mixture_vs_bass_stem(
    mixture_audio: np.ndarray,
    bass_stem_audio: np.ndarray,
    sample_rate: int,
    reference_midi_paths: list[Path],
    *,
    excerpt_seconds: float,
) -> BassAmtComparison:
    """Compare the same production AMT engine before and after bass separation."""
    return BassAmtComparison(
        mixture=score_basic_pitch_audio(
            mixture_audio,
            sample_rate,
            reference_midi_paths,
            excerpt_seconds=excerpt_seconds,
        ),
        bass_stem=score_basic_pitch_audio(
            bass_stem_audio,
            sample_rate,
            reference_midi_paths,
            excerpt_seconds=excerpt_seconds,
        ),
    )
