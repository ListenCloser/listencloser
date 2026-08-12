"""GuitarSet dataset adapter (real guitar, mono-mic audio + JAMS notes).

Source:   https://zenodo.org/records/3371780
Version:  GuitarSet (Zenodo record 3371780)
License:  CC BY 4.0
Split:    test (fold 0)
Redistribution: do NOT commit audio/annotations to git; download to cache.

Download layout (verified):
  annotation.zip          39.1 MB  md5:b39b78e63d3446f2e54ddb7a54df9b10
  audio_mono-mic.zip     656.9 MB  md5:275966d6610ac34999b58426beb119c3
"""

from __future__ import annotations

import zipfile
from typing import Any

from evaluation.datasets import cache
from evaluation.datasets._download import download
from evaluation.datasets.parsers import parse_guitarset_jams
from evaluation.datasets.registry import (
    DatasetAdapter,
    ManualAcquisitionError,
    ResolvedClip,
)

_ANNOTATION_URL = "https://zenodo.org/records/3371780/files/annotation.zip?download=1"
_AUDIO_URL = "https://zenodo.org/records/3371780/files/audio_mono-mic.zip?download=1"


class GuitarSetAdapter(DatasetAdapter):
    name = "guitarset"
    license = "CC BY 4.0"

    def resolve(self, clip: dict[str, Any]) -> ResolvedClip:
        ddir = cache.dataset_dir("guitarset")
        source_id = clip["source_id"]  # e.g. "00_Rock2-142-D_comp"

        audio_dest = ddir / "audio" / f"{source_id}_mic.wav"
        if not audio_dest.exists():
            audio_zip = download(_AUDIO_URL, ddir / "audio_mono-mic.zip")
            with zipfile.ZipFile(audio_zip) as zf:
                member = f"{source_id}_mic.wav"
                if member not in zf.namelist():
                    raise ManualAcquisitionError(
                        f"GuitarSet audio '{member}' not found in audio_mono-mic.zip."
                    )
                audio_dest.parent.mkdir(parents=True, exist_ok=True)
                audio_dest.write_bytes(zf.read(member))

        ann_dest = ddir / "annotation" / f"{source_id}.jams"
        if not ann_dest.exists():
            ann_zip = download(_ANNOTATION_URL, ddir / "annotation.zip")
            with zipfile.ZipFile(ann_zip) as zf:
                member = f"{source_id}.jams"
                if member not in zf.namelist():
                    raise ManualAcquisitionError(
                        f"GuitarSet annotation '{member}' not found in annotation.zip."
                    )
                ann_dest.parent.mkdir(parents=True, exist_ok=True)
                ann_dest.write_bytes(zf.read(member))

        return ResolvedClip(
            audio_path=str(audio_dest),
            annotations_path=str(ann_dest),
        )


def load_guitarset_notes(jams_path: str) -> list[dict[str, Any]]:
    with open(jams_path) as fh:
        return parse_guitarset_jams(fh.read())
