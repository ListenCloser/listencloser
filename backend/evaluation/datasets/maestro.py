"""MAESTRO v3.0.0 dataset adapter (solo piano, audio + aligned MIDI).

Source:   https://magenta.tensorflow.org/datasets/maestro
Version:  v3.0.0
License:  CC BY-NC-SA 4.0 (non-commercial)
Split:    test
Redistribution: do NOT commit audio/MIDI to git; download to cache only.

The official distribution ships metadata (maestro-v3.0.0.json) and per-split
ZIP archives. This adapter resolves individual clips from the test split.
"""

from __future__ import annotations

from typing import Any

from evaluation.datasets import cache
from evaluation.datasets._download import download
from evaluation.datasets.registry import DatasetAdapter, ManualAcquisitionError, ResolvedClip

_METADATA_URL = (
    "https://storage.googleapis.com/magentadata/datasets/maestro/v3.0.0/maestro-v3.0.0.json"
)


class MaestroAdapter(DatasetAdapter):
    name = "maestro"
    license = "CC BY-NC-SA 4.0"

    def resolve(self, clip: dict[str, Any]) -> ResolvedClip:
        # MAESTRO audio/MIDI URLs are encoded in the metadata file by filename.
        # The manifest pins a source_id (filename stem); we download the
        # metadata, locate the matching entry, then fetch audio + midi.
        import json

        ddir = cache.dataset_dir("maestro")
        meta_path = download(_METADATA_URL, ddir / "maestro-v3.0.0.json")

        with open(meta_path) as fh:
            meta = json.load(fh)
        source_id = clip["source_id"]
        entry = next(
            (
                e
                for e in meta.get("test", [])
                if e.get("midi_filename", "").split("/")[-1].startswith(source_id)
                or source_id in e.get("midi_filename", "")
            ),
            None,
        )
        if entry is None:
            raise ManualAcquisitionError(
                f"MAESTRO test entry '{source_id}' not found in metadata. "
                f"Verify the source_id against maestro-v3.0.0.json."
            )

        audio_url = entry["audio_filename"]
        midi_url = entry["midi_filename"]
        audio_name = audio_url.split("/")[-1]
        midi_name = midi_url.split("/")[-1]
        audio_path = download(audio_url, ddir / audio_name)
        midi_path = download(midi_url, ddir / midi_name)
        return ResolvedClip(audio_path=str(audio_path), reference_midi_path=str(midi_path))
