"""MidiBERT-Piano symbolic Melody adapter.

The pinned upstream CP tokenizer/model/inference code is used directly. Its
quantized reconstruction is deliberately not used as product timing: predicted
classes are attached back to the exact source-MIDI note sequence before
publication.

Upstream: https://github.com/wazenmai/MIDI-BERT
Pinned revision: 0b935584f641d3d59a8e6aff2f334b425ce1542d
Code license: MIT
"""

from __future__ import annotations

import hashlib
import os
import pickle
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import miditoolkit
import numpy as np
import pretty_midi
import torch

from engines.base import EngineProvenance, MelodyEngine, MelodyResult

_UPSTREAM_REVISION = "0b935584f641d3d59a8e6aff2f334b425ce1542d"
_DEFAULT_ROOT = "/opt/midibert"
_DEFAULT_CHECKPOINT = "/opt/midibert-models/melody_default/model_best.ckpt"
_DEFAULT_DICT = "/opt/midibert/data_creation/prepare_data/dict/CP.pkl"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _source_notes(path: Path) -> list[dict[str, Any]]:
    """Return notes in the exact ordering used by upstream ``read_items``."""
    midi = miditoolkit.MidiFile(str(path))
    ordered = []
    for instrument in midi.instruments:
        if instrument.is_drum:
            continue
        notes = sorted(instrument.notes, key=lambda note: (note.start, note.pitch))
        ordered.extend(notes)
    ordered.sort(key=lambda note: note.start)

    performance = pretty_midi.PrettyMIDI(str(path))
    return [
        {
            "pitch": note.pitch,
            "start_seconds": float(performance.tick_to_time(note.start)),
            "end_seconds": float(performance.tick_to_time(note.end)),
            "velocity": note.velocity,
        }
        for note in ordered
    ]


def _summarize(selected: list[dict[str, Any]], candidate_count: int) -> dict[str, Any] | None:
    if len(selected) < 2:
        return None
    pitches = [int(note["pitch"]) for note in selected]
    intervals = [abs(b - a) for a, b in zip(pitches, pitches[1:], strict=False)]
    nonzero = [interval for interval in intervals if interval > 0]
    low, high = min(pitches), max(pitches)
    return {
        "low_pitch": low,
        "high_pitch": high,
        "range_semitones": high - low,
        "unique_pitch_classes": len({pitch % 12 for pitch in pitches}),
        "stepwise_ratio": (
            round(sum(iv <= 2 for iv in nonzero) / len(nonzero), 3) if nonzero else 0.0
        ),
        "leap_ratio": (
            round(sum(iv >= 5 for iv in nonzero) / len(nonzero), 3) if nonzero else 0.0
        ),
        "heuristic": "midibert_piano_cp",
        "candidate_note_count": candidate_count,
        "selected_note_count": len(selected),
        "evaluated_start_seconds": round(min(float(n["start_seconds"]) for n in selected), 4),
        "evaluated_end_seconds": round(max(float(n["end_seconds"]) for n in selected), 4),
        "notes": [
            {
                "pitch": int(note["pitch"]),
                "start_seconds": round(float(note["start_seconds"]), 4),
                "end_seconds": round(float(note["end_seconds"]), 4),
                "velocity": int(note["velocity"]),
                "model_class": str(note["model_class"]),
            }
            for note in selected
        ],
    }


class MidiBERTMelodyEngine(MelodyEngine):
    """Official MidiBERT-Piano CP melody inference behind ``MelodyEngine``."""

    ENGINE = "midibert"

    def __init__(
        self,
        *,
        root: str | None = None,
        checkpoint: str | None = None,
        dict_file: str | None = None,
        checkpoint_sha256: str | None = None,
    ) -> None:
        self.root = Path(root or os.getenv("MIDIBERT_ROOT", _DEFAULT_ROOT))
        self.checkpoint = Path(
            checkpoint or os.getenv("MIDIBERT_CHECKPOINT", _DEFAULT_CHECKPOINT)
        )
        self.dict_file = Path(dict_file or os.getenv("MIDIBERT_DICT", _DEFAULT_DICT))
        self.expected_checkpoint_sha256 = checkpoint_sha256 or os.getenv(
            "MIDIBERT_CHECKPOINT_SHA256"
        )

    @property
    def provenance(self) -> EngineProvenance:
        parameters: dict[str, Any] = {
            "source_revision": _UPSTREAM_REVISION,
            "representation": "CP",
            "max_seq_len": 512,
            "hidden_size": 768,
            "bridge_as_melody": True,
            "timing_publication": "exact_source_midi_notes",
            "validated_domain": "POP909-style symbolic piano/pop",
        }
        if self.expected_checkpoint_sha256:
            parameters["checkpoint_sha256"] = self.expected_checkpoint_sha256
        return EngineProvenance(
            engine=self.ENGINE,
            library_version=_UPSTREAM_REVISION,
            model="MidiBERT-Piano CP melody_default",
            parameters=parameters,
        )

    def _validate_runtime(self) -> None:
        required = [
            self.root / "melody_extraction/midibert/extract.py",
            self.root / "melody_extraction/midibert/midi2CP.py",
            self.root / "MidiBERT/model.py",
            self.checkpoint,
            self.dict_file,
        ]
        missing = [path for path in required if not path.is_file()]
        if missing:
            raise RuntimeError(
                "MidiBERT runtime is incomplete; missing pinned source/model assets: "
                + ", ".join(str(path) for path in missing)
            )
        if not self.expected_checkpoint_sha256:
            raise RuntimeError("MidiBERT checkpoint SHA-256 is not pinned")
        actual = _sha256(self.checkpoint)
        if actual != self.expected_checkpoint_sha256:
            raise RuntimeError(
                "MidiBERT checkpoint checksum mismatch: expected "
                f"{self.expected_checkpoint_sha256}, got {actual}"
            )

    def _predict_classes(self, input_path: Path) -> list[int]:
        """Run the pinned upstream CP preprocessing/model/inference implementation."""
        if str(self.root) not in sys.path:
            sys.path.insert(0, str(self.root))
        if not hasattr(np, "int"):
            np.int = int  # type: ignore[attr-defined]

        from melody_extraction.midibert.extract import inference, load_model
        from melody_extraction.midibert.midi2CP import CP

        with self.dict_file.open("rb") as handle:
            e2w, w2e = pickle.load(handle)
        compact = ["Bar", "Position", "Pitch", "Duration"]
        pad_cp = [e2w[kind][f"{kind} <PAD>"] for kind in compact]
        cp_model = CP(dict=str(self.dict_file))
        events, tokens = cp_model.prepare_data(str(input_path), 512)

        args = SimpleNamespace(max_seq_len=512, hs=768, ckpt=str(self.checkpoint))
        model = load_model(args, e2w, w2e)
        model.eval()
        with torch.no_grad():
            predictions = inference(model, tokens, pad_cp, torch.device("cpu"))

        note_event_count = sum(1 for event in events if len(event) == 5)
        flattened = predictions.reshape(-1).tolist()
        if note_event_count > len(flattened):
            raise RuntimeError("MidiBERT returned fewer note labels than input note events")
        return [int(value) for value in flattened[:note_event_count]]

    def analyze(self, midi_bytes: bytes, **kwargs: Any) -> MelodyResult:
        self._validate_runtime()
        with tempfile.TemporaryDirectory(prefix="listencloser-midibert-") as tempdir:
            input_path = Path(tempdir) / "input.mid"
            input_path.write_bytes(midi_bytes)
            source = _source_notes(input_path)
            if len(source) < 2:
                return MelodyResult(melody=None, provenance=self.provenance)
            classes = self._predict_classes(input_path)

        if len(classes) != len(source):
            raise RuntimeError(
                "MidiBERT note-label count does not match exact source note count: "
                f"{len(classes)} labels for {len(source)} notes"
            )

        selected: list[dict[str, Any]] = []
        for note, label in zip(source, classes, strict=True):
            if label not in (1, 2):
                continue
            selected.append({**note, "model_class": "melody" if label == 1 else "bridge"})

        return MelodyResult(melody=_summarize(selected, len(source)), provenance=self.provenance)
