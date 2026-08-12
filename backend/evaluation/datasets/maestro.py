"""MAESTRO v3.0.0 dataset adapter (solo piano, audio + aligned MIDI).

Source:   https://magenta.tensorflow.org/datasets/maestro
Version:  v3.0.0
License:  CC BY-NC-SA 4.0 (non-commercial)
Split:    test
Redistribution: do NOT commit audio/MIDI to git; download to cache only.

MAESTRO v3.0.0 metadata (``maestro-v3.0.0.json``) is a single JSON object keyed
by an index string. Each value has ``split``, ``midi_filename``, and
``audio_filename`` fields. Those filenames are dataset-relative paths
(e.g. ``2004/MIDI-Unprocessed_...wav.midi``); the full URL is the base URL plus
the relative path. This adapter parses that schema and downloads the matched
test-split clip.
"""

from __future__ import annotations

from typing import Any

from evaluation.datasets import cache
from evaluation.datasets._download import download
from evaluation.datasets.registry import (
    DatasetAdapter,
    ManualAcquisitionError,
    ResolvedClip,
)

_BASE_URL = "https://storage.googleapis.com/magentadata/datasets/maestro/v3.0.0"
_METADATA_URL = f"{_BASE_URL}/maestro-v3.0.0.json"


def find_test_entry(meta: Any, source_id: str) -> dict[str, Any] | None:
    """Locate a MAESTRO test-split entry by matching its midi_filename.

    ``meta`` is the parsed maestro-v3.0.0.json object (dict keyed by index).
    Returns the entry dict, or None when no test entry matches.
    """
    if not isinstance(meta, dict):
        return None
    for e in meta.values():
        if (
            isinstance(e, dict)
            and e.get("split") == "test"
            and source_id in e.get("midi_filename", "")
        ):
            return e
    return None


class MaestroAdapter(DatasetAdapter):
    name = "maestro"
    license = "CC BY-NC-SA 4.0"

    def resolve(self, clip: dict[str, Any]) -> ResolvedClip:
        ddir = cache.dataset_dir("maestro")
        meta_path = download(_METADATA_URL, ddir / "maestro-v3.0.0.json")

        import json

        with open(meta_path) as fh:
            meta = json.load(fh)

        source_id = clip["source_id"]
        entry = find_test_entry(meta, source_id)
        if entry is None:
            raise ManualAcquisitionError(
                f"MAESTRO test entry containing '{source_id}' not found in "
                f"maestro-v3.0.0.json. Verify the source_id against the official "
                f"test split."
            )

        audio_rel = entry["audio_filename"]
        midi_rel = entry["midi_filename"]
        audio_path = download(f"{_BASE_URL}/{audio_rel}", ddir / audio_rel.split("/")[-1])
        midi_path = download(f"{_BASE_URL}/{midi_rel}", ddir / midi_rel.split("/")[-1])
        return ResolvedClip(audio_path=str(audio_path), reference_midi_path=str(midi_path))
