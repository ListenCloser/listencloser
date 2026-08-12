"""Slakh2100 dataset adapter (multi-instrument mixture transcription).

Source:   https://zenodo.org/record/4599666
Version:  Slakh2100 (flac + midi, synthesized from LMD)
License:  CC BY 4.0 (synthesized audio; underlying MIDI from the Lakh dataset)
Split:    test

Slakh2100 provides multi-track MIDI + rendered mixtures. Used here for
full-mix transcription quality outside solo piano.
"""

from __future__ import annotations

from typing import Any

from evaluation.datasets import cache
from evaluation.datasets.registry import DatasetAdapter, ManualAcquisitionError, ResolvedClip


class SlakhAdapter(DatasetAdapter):
    name = "slakh"
    license = "CC BY 4.0"

    def resolve(self, clip: dict[str, Any]) -> ResolvedClip:
        ddir = cache.dataset_dir("slakh")
        source_id = clip["source_id"]  # e.g. "Track00001"
        audio_rel = clip.get("audio_rel") or f"{source_id}/mix.flac"
        midi_rel = clip.get("midi_rel") or f"{source_id}/all_src.mid"
        audio_path = ddir / "test" / audio_rel
        midi_path = ddir / "test" / midi_rel

        missing = [str(p) for p in (audio_path, midi_path) if not p.exists()]
        if missing:
            raise ManualAcquisitionError(
                "Slakh2100 requires manual acquisition. Download the test split "
                "from Zenodo record 4599666 into slakh/test/. "
                "Missing: " + ", ".join(missing)
            )

        return ResolvedClip(
            audio_path=str(audio_path),
            reference_midi_path=str(midi_path),
        )
