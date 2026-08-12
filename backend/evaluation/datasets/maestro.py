"""MAESTRO v3.0.0 dataset adapter (solo piano, audio + aligned MIDI).

Source:   https://magenta.tensorflow.org/datasets/maestro
Version:  v3.0.0
License:  CC BY-NC-SA 4.0 (confirmed on the dataset page)
Split:    test (177 performances)
Redistribution: do NOT commit audio/MIDI to git; download to cache only.

MAESTRO v3.0.0 distribution (verified against the dataset page):
  - maestro-v3.0.0.json        metadata (columnar; 7 keys keyed by index)
  - maestro-v3.0.0-midi.zip    56 MB — all MIDI (files under ``maestro-v3.0.0/``)
  - maestro-v3.0.0.zip         101 GB — audio + MIDI (audio is NOT served as
                                individual files, only inside this archive)

The adapter downloads metadata + the MIDI zip and extracts the reference MIDI.
Audio requires the 101 GB archive, which is NOT auto-downloaded; the adapter
raises ManualAcquisitionError directing the user to extract audio into the cache.
"""

from __future__ import annotations

import zipfile
from pathlib import Path
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
_MIDI_ZIP_URL = f"{_BASE_URL}/maestro-v3.0.0-midi.zip"


def find_test_entry(meta: Any, source_id: str) -> dict[str, Any] | None:
    """Locate a MAESTRO test-split entry by its midi_filename.

    ``meta`` is the parsed columnar maestro-v3.0.0.json object. ``source_id`` is
    the exact relative ``midi_filename`` (or a unique suffix of it). Returns a
    dict with ``midi_filename``/``audio_filename`` for the matched index, or
    None when no test entry matches.
    """
    if not isinstance(meta, dict):
        return None
    split = meta.get("split")
    midi = meta.get("midi_filename")
    audio = meta.get("audio_filename")
    if not (isinstance(split, dict) and isinstance(midi, dict) and isinstance(audio, dict)):
        return None
    for idx, s in split.items():
        if s != "test":
            continue
        m = midi.get(idx)
        if m is not None and (source_id == m or m.endswith(source_id)):
            return {
                "midi_filename": m,
                "audio_filename": audio.get(idx, ""),
            }
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
                f"MAESTRO test entry matching '{source_id}' not found in "
                f"maestro-v3.0.0.json. Verify the source_id against the official "
                f"test split."
            )

        midi_rel = entry["midi_filename"]  # e.g. "2008/MIDI-...wav.midi"
        audio_rel = entry["audio_filename"]  # e.g. "2008/MIDI-...wav.wav"

        # MIDI: extract from the 56 MB midi-only zip (files are under
        # "maestro-v3.0.0/" inside the archive).
        midi_dest = ddir / "midi" / Path(midi_rel).name
        if not midi_dest.exists():
            midi_zip = download(_MIDI_ZIP_URL, ddir / "maestro-v3.0.0-midi.zip")
            with zipfile.ZipFile(midi_zip) as zf:
                zf_path = f"maestro-v3.0.0/{midi_rel}"
                if zf_path not in zf.namelist():
                    raise ManualAcquisitionError(
                        f"MIDI '{midi_rel}' not found inside maestro-v3.0.0-midi.zip."
                    )
                midi_dest.parent.mkdir(parents=True, exist_ok=True)
                midi_dest.write_bytes(zf.read(zf_path))

        # Audio: only distributed inside the 101 GB maestro-v3.0.0.zip. Require
        # the user to extract it (or the full archive) into the cache.
        audio_dest = ddir / "audio" / Path(audio_rel).name
        if not audio_dest.exists():
            raise ManualAcquisitionError(
                "MAESTRO audio is only distributed inside the 101 GB "
                "maestro-v3.0.0.zip (individual WAVs are not served). Download "
                "that archive and extract the audio into MUSIC_EVAL_CACHE_DIR/"
                f"maestro/audio/{Path(audio_rel).name}. MIDI reference is already "
                "available."
            )

        return ResolvedClip(
            audio_path=str(audio_dest),
            reference_midi_path=str(midi_dest),
        )
