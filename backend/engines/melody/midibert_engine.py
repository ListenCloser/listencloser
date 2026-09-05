"""MidiBERT-Piano symbolic Melody adapter.

The upstream model is intentionally executed through its pinned official source
rather than reimplementing its CP tokenizer/model stack here.  The upstream
output MIDI is used only to identify selected notes; ListenCloser republishes
the exact source-MIDI note timing/velocity so quantized reconstruction never
becomes a second coordinate authority.

Upstream: https://github.com/wazenmai/MIDI-BERT
Pinned source revision: 0b935584f641d3d59a8e6aff2f334b425ce1542d
Code license: MIT
"""

from __future__ import annotations

import io
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import Any

import pretty_midi

from engines.base import EngineProvenance, MelodyEngine, MelodyResult

_UPSTREAM_REVISION = "0b935584f641d3d59a8e6aff2f334b425ce1542d"
_DEFAULT_ROOT = "/opt/midibert"
_DEFAULT_CHECKPOINT = "/opt/midibert-models/melody_default/model_best.ckpt"
_DEFAULT_DICT = "/opt/midibert/data_creation/prepare_data/dict/CP.pkl"


def _source_notes(midi_bytes: bytes) -> list[pretty_midi.Note]:
    pm = pretty_midi.PrettyMIDI(io.BytesIO(midi_bytes))
    notes = [note for inst in pm.instruments if not inst.is_drum for note in inst.notes]
    notes.sort(key=lambda note: (note.start, note.pitch, note.end, note.velocity))
    return notes


def _map_selected_notes(
    source: list[pretty_midi.Note], predicted: list[pretty_midi.Note]
) -> list[pretty_midi.Note]:
    """Map upstream's quantized selected-note MIDI back to exact source notes.

    MidiBERT's postprocessor preserves note order while reconstructing timing on
    a 4/4 CP grid.  Match the selected pitch sequence as a monotonic subsequence
    of the exact source candidates.  Ambiguity that prevents a complete mapping
    fails closed rather than publishing reconstructed/approximate time.
    """
    selected: list[pretty_midi.Note] = []
    cursor = 0
    for predicted_note in predicted:
        match = None
        for index in range(cursor, len(source)):
            if source[index].pitch == predicted_note.pitch:
                match = index
                break
        if match is None:
            raise RuntimeError(
                "MidiBERT selected-note mapping could not preserve exact source MIDI identity"
            )
        selected.append(source[match])
        cursor = match + 1
    return selected


def _summarize(selected: list[pretty_midi.Note], candidate_count: int) -> dict[str, Any] | None:
    if len(selected) < 2:
        return None
    pitches = [note.pitch for note in selected]
    intervals = [abs(b - a) for a, b in zip(pitches, pitches[1:])]
    nonzero = [interval for interval in intervals if interval > 0]
    low, high = min(pitches), max(pitches)
    return {
        "low_pitch": low,
        "high_pitch": high,
        "range_semitones": high - low,
        "unique_pitch_classes": len({pitch % 12 for pitch in pitches}),
        "stepwise_ratio": round(sum(interval <= 2 for interval in nonzero) / len(nonzero), 3)
        if nonzero
        else 0.0,
        "leap_ratio": round(sum(interval >= 5 for interval in nonzero) / len(nonzero), 3)
        if nonzero
        else 0.0,
        "heuristic": "midibert_piano_cp",
        "candidate_note_count": candidate_count,
        "selected_note_count": len(selected),
        "evaluated_start_seconds": round(min(note.start for note in selected), 4),
        "evaluated_end_seconds": round(max(note.end for note in selected), 4),
        "notes": [
            {
                "pitch": note.pitch,
                "start_seconds": round(note.start, 4),
                "end_seconds": round(note.end, 4),
                "velocity": note.velocity,
            }
            for note in selected
        ],
    }


class MidiBERTMelodyEngine(MelodyEngine):
    """Official MidiBERT-Piano CP melody inference behind MelodyEngine."""

    ENGINE = "midibert"

    def __init__(
        self,
        *,
        root: str | None = None,
        checkpoint: str | None = None,
        dict_file: str | None = None,
    ) -> None:
        self.root = Path(root or os.getenv("MIDIBERT_ROOT", _DEFAULT_ROOT))
        self.checkpoint = Path(
            checkpoint or os.getenv("MIDIBERT_CHECKPOINT", _DEFAULT_CHECKPOINT)
        )
        self.dict_file = Path(dict_file or os.getenv("MIDIBERT_DICT", _DEFAULT_DICT))

    @property
    def provenance(self) -> EngineProvenance:
        return EngineProvenance(
            engine=self.ENGINE,
            library_version=_UPSTREAM_REVISION,
            model="MidiBERT-Piano CP melody_default",
            parameters={
                "source_revision": _UPSTREAM_REVISION,
                "representation": "CP",
                "max_seq_len": 512,
                "hidden_size": 768,
                "bridge_as_melody": True,
                "timing_publication": "exact_source_midi_notes",
                "checkpoint_path": str(self.checkpoint),
            },
        )

    def _validate_runtime(self) -> Path:
        script = self.root / "melody_extraction/midibert/extract.py"
        missing = [path for path in (script, self.checkpoint, self.dict_file) if not path.is_file()]
        if missing:
            raise RuntimeError(
                "MidiBERT runtime is incomplete; missing pinned source/model assets: "
                + ", ".join(str(path) for path in missing)
            )
        return script

    def analyze(self, midi_bytes: bytes, **kwargs: Any) -> MelodyResult:
        script = self._validate_runtime()
        source_notes = _source_notes(midi_bytes)
        if len(source_notes) < 2:
            return MelodyResult(melody=None, provenance=self.provenance)

        with tempfile.TemporaryDirectory(prefix="listencloser-midibert-") as tempdir:
            input_path = Path(tempdir) / "input.mid"
            output_path = Path(tempdir) / "melody.mid"
            input_path.write_bytes(midi_bytes)
            command = [
                sys.executable,
                str(script),
                "--input_path",
                str(input_path),
                "--output_path",
                str(output_path),
                "--dict_file",
                str(self.dict_file),
                "--ckpt",
                str(self.checkpoint),
                "--cpu",
                "--bridge",
                "True",
            ]
            completed = subprocess.run(
                command,
                cwd=self.root,
                capture_output=True,
                text=True,
                timeout=300,
                check=False,
            )
            if completed.returncode != 0:
                detail = (completed.stderr or completed.stdout).strip()[-2000:]
                raise RuntimeError(f"MidiBERT melody inference failed: {detail}")
            if not output_path.is_file():
                raise RuntimeError("MidiBERT completed without publishing a melody MIDI")

            predicted_pm = pretty_midi.PrettyMIDI(str(output_path))
            predicted_notes = [
                note
                for inst in predicted_pm.instruments
                if not inst.is_drum
                for note in inst.notes
            ]
            predicted_notes.sort(key=lambda note: (note.start, note.pitch, note.end, note.velocity))

        selected = _map_selected_notes(source_notes, predicted_notes)
        return MelodyResult(
            melody=_summarize(selected, len(source_notes)),
            provenance=self.provenance,
        )
