"""Downstream MIR metrics for separated stems.

These helpers intentionally call the same production/evaluation engines used by
hello-ai. The separation bakeoff is meant to measure whether a stem improves a
real downstream task, not whether it helps an easier proxy detector.
"""

from __future__ import annotations

import io
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import soundfile as sf


@dataclass(frozen=True)
class DownstreamMetrics:
    chord_accuracy: float | None = None
    beat_f1: float | None = None
    melody_accuracy: float | None = None
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "chord_accuracy": round(self.chord_accuracy, 4)
            if self.chord_accuracy is not None
            else None,
            "beat_f1": round(self.beat_f1, 4) if self.beat_f1 is not None else None,
            "melody_accuracy": round(self.melody_accuracy, 4)
            if self.melody_accuracy is not None
            else None,
            "notes": self.notes,
        }


@dataclass(frozen=True)
class DownstreamDelta:
    """A mixture-vs-stem comparison for one downstream metric."""

    mixture_score: float
    stem_score: float

    @property
    def delta(self) -> float:
        return self.stem_score - self.mixture_score

    def to_dict(self) -> dict[str, float]:
        return {
            "mixture_score": round(self.mixture_score, 4),
            "stem_score": round(self.stem_score, 4),
            "delta": round(self.delta, 4),
        }


def _audio_to_wav_bytes(audio: np.ndarray, sample_rate: int) -> bytes:
    samples = np.asarray(audio, dtype=np.float32)
    if samples.ndim == 2:
        # Adapters may return channel-first stereo. Production beat estimation
        # accepts normal WAV channel layout and performs its own mono fold-down.
        if samples.shape[0] <= 8 and samples.shape[0] < samples.shape[1]:
            samples = samples.T
        elif samples.shape[1] > 8:
            raise ValueError(f"Unsupported audio shape for WAV encoding: {samples.shape}")
    elif samples.ndim != 1:
        raise ValueError(f"Unsupported audio rank for WAV encoding: {samples.ndim}")

    buffer = io.BytesIO()
    sf.write(buffer, samples, sample_rate, format="WAV", subtype="FLOAT")
    return buffer.getvalue()


def _load_midi_events(paths: list[Path]):
    import pretty_midi

    from backend.evaluation.analysis_v3.multitrack_transcription.metrics import NoteEvent

    events: list[NoteEvent] = []
    for path in paths:
        midi = pretty_midi.PrettyMIDI(str(path))
        for instrument in midi.instruments:
            for note in instrument.notes:
                events.append(
                    NoteEvent(
                        pitch=int(note.pitch),
                        start=float(note.start),
                        end=float(note.end),
                        program=int(instrument.program),
                        is_drum=bool(instrument.is_drum),
                    )
                )
    return events


def compute_chord_accuracy_on_stem(
    stem_audio: np.ndarray,
    sample_rate: int,
    reference_chords: list[dict[str, Any]] | None = None,
) -> float | None:
    """Compute chord accuracy on a separated stem.

    Not yet implemented: #334 should only score this once the existing chord
    engine's output can be aligned against a rights-safe annotated corpus.
    """
    return None


def compute_beat_f1_on_stem(
    stem_audio: np.ndarray,
    sample_rate: int,
    reference_beats: list[float] | None = None,
) -> float | None:
    """Score the production beat estimator on mixture or stem audio.

    Uses the exact production baseline, ``music_features.estimate_beat_grid``,
    and the canonical Analysis V3 beat metric from #335:
    ``mir_eval.beat.f_measure(..., f_measure_threshold=0.07)``.
    """
    if not reference_beats:
        return None

    try:
        import mir_eval
    except ImportError as exc:  # pragma: no cover - benchmark environment guard
        raise RuntimeError(
            "mir_eval is required for the separation downstream beat benchmark"
        ) from exc

    from music_features import estimate_beat_grid

    _, estimated_beats = estimate_beat_grid(_audio_to_wav_bytes(stem_audio, sample_rate))
    reference = np.asarray(reference_beats, dtype=float)
    estimated = np.asarray(estimated_beats, dtype=float)
    return float(
        mir_eval.beat.f_measure(
            reference,
            estimated,
            f_measure_threshold=0.07,
        )
    )


def compare_beat_f1_mixture_vs_stem(
    mixture_audio: np.ndarray,
    stem_audio: np.ndarray,
    sample_rate: int,
    reference_beats: list[float] | None,
) -> DownstreamDelta | None:
    """Return the beat-F1 gain/loss from using a separated drum stem."""
    if not reference_beats:
        return None

    mixture_score = compute_beat_f1_on_stem(mixture_audio, sample_rate, reference_beats)
    stem_score = compute_beat_f1_on_stem(stem_audio, sample_rate, reference_beats)
    if mixture_score is None or stem_score is None:
        return None
    return DownstreamDelta(mixture_score=mixture_score, stem_score=stem_score)


def compute_bass_note_f1_on_audio(
    audio: np.ndarray,
    sample_rate: int,
    reference_midi_paths: list[Path] | None,
) -> float | None:
    """Score production Basic Pitch against isolated bass reference MIDI.

    The metric is the existing Analysis V3 flat onset-note F1 contract: mir_eval
    note matching at the repository's canonical tolerances, with program labels
    ignored because production Basic Pitch is instrument-agnostic.
    """
    if not reference_midi_paths:
        return None

    from backend.evaluation.analysis_v3.multitrack_transcription.adapters.basic_pitch import (
        run_basic_pitch,
    )
    from backend.evaluation.analysis_v3.multitrack_transcription.metrics import match_notes

    for path in reference_midi_paths:
        if not path.is_file():
            raise ValueError(f"Missing bass reference MIDI: {path}")

    with tempfile.TemporaryDirectory(prefix="hello-ai-separation-bass-") as temp_dir:
        temp_root = Path(temp_dir)
        audio_path = temp_root / "input.wav"
        prediction_path = temp_root / "prediction.mid"
        audio_path.write_bytes(_audio_to_wav_bytes(audio, sample_rate))
        run_basic_pitch(audio_path, prediction_path)
        reference = _load_midi_events(reference_midi_paths)
        predicted = _load_midi_events([prediction_path])
        return float(match_notes(reference, predicted).f1)


def compare_bass_note_f1_mixture_vs_stem(
    mixture_audio: np.ndarray,
    bass_stem_audio: np.ndarray,
    sample_rate: int,
    reference_midi_paths: list[Path] | None,
) -> DownstreamDelta | None:
    """Measure whether a separated bass stem improves production AMT F1."""
    if not reference_midi_paths:
        return None

    mixture_score = compute_bass_note_f1_on_audio(
        mixture_audio,
        sample_rate,
        reference_midi_paths,
    )
    stem_score = compute_bass_note_f1_on_audio(
        bass_stem_audio,
        sample_rate,
        reference_midi_paths,
    )
    if mixture_score is None or stem_score is None:
        return None
    return DownstreamDelta(mixture_score=mixture_score, stem_score=stem_score)


def compute_melody_accuracy_on_stem(
    stem_audio: np.ndarray,
    sample_rate: int,
    reference_melody: list[dict[str, Any]] | None = None,
) -> float | None:
    """Compute melody accuracy on a separated stem.

    Not yet implemented: a vocal/lead evaluation still needs a corpus whose
    reference melody aligns with the selected source-separation target.
    """
    return None
