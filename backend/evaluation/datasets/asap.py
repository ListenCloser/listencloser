"""ASAP dataset adapter (real piano performance ↔ aligned score).

Source:   https://github.com/fosfrancesco/asap-dataset
Version:  repository snapshot (performance MIDI + score MIDI + MusicXML)
License:  CC BY-NC-SA 4.0 (verify against the repository LICENSE before redistribution)
Split:    subset of published pieces (no official train/test split)

ASAP links performance audio/notes to aligned beat/downbeat annotations and
score-derived MusicXML. Audio is distributed separately from the metadata
repository; this adapter documents the layout and requires either direct audio
download or manual placement.
"""

from __future__ import annotations

from typing import Any

from evaluation.datasets import cache
from evaluation.datasets.registry import DatasetAdapter, ManualAcquisitionError, ResolvedClip


class AsapAdapter(DatasetAdapter):
    name = "asap"
    license = "CC BY-NC-SA 4.0 (verify)"

    def resolve(self, clip: dict[str, Any]) -> ResolvedClip:
        # ASAP layout: asap-dataset/<performer>/<piece>/ with
        #   <piece>_annotations.txt  (beat/downbeat)
        #   <piece>.mid              (performance MIDI)
        #   <piece>.musicxml         (score)
        #   audio/                   (audio, distributed separately)
        # The manifest pins source_id = "<performer>/<piece>".
        ddir = cache.dataset_dir("asap")
        source_id = clip["source_id"]
        midi_rel = f"{source_id}.mid"
        xml_rel = f"{source_id}.musicxml"
        beats_rel = f"{source_id}_annotations.txt"

        midi_path = ddir / midi_rel
        xml_path = ddir / xml_rel
        beats_path = ddir / beats_rel
        audio_rel = clip.get("audio_rel") or f"{source_id}.wav"
        audio_path = ddir / "audio" / audio_rel

        missing = [str(p) for p in (audio_path, midi_path) if not p.exists()]
        if missing:
            raise ManualAcquisitionError(
                "ASAP requires manual acquisition. Clone the dataset repository "
                "into MUSIC_EVAL_CACHE_DIR/asap and place audio under "
                "asap/audio/. Missing: " + ", ".join(missing)
            )

        return ResolvedClip(
            audio_path=str(audio_path),
            reference_midi_path=str(midi_path),
            reference_musicxml_path=str(xml_path) if xml_path.exists() else None,
            beats_path=str(beats_path) if beats_path.exists() else None,
        )
