"""BabySlakh dataset adapter (multi-instrument mixture transcription).

Source:   https://zenodo.org/records/4603870
Version:  BabySlakh (first 20 Slakh tracks)
License:  CC BY 4.0
Split:    none (fixed 20-track subset)
Redistribution: do NOT commit audio/MIDI to git; download to cache.

Download layout (verified):
  babyslakh_16k.tar.gz  882.8 MB  md5:311096dc2bde7d61c97e930edbfc7f78

Each track directory contains ``mix.wav`` (16 kHz mono mixture) and
``all_src.mid`` (aligned multi-track MIDI). Drum tracks are ``is_drum`` and are
excluded from pitched-note transcription metrics.
"""

from __future__ import annotations

import tarfile
from pathlib import Path
from typing import Any

from evaluation.datasets import cache
from evaluation.datasets._download import download
from evaluation.datasets.parsers import parse_babyslakh_midi
from evaluation.datasets.registry import (
    DatasetAdapter,
    ManualAcquisitionError,
    ResolvedClip,
)

_TAR_URL = "https://zenodo.org/records/4603870/files/babyslakh_16k.tar.gz?download=1"


class BabySlakhAdapter(DatasetAdapter):
    name = "babyslakh"
    license = "CC BY 4.0"

    def resolve(self, clip: dict[str, Any]) -> ResolvedClip:
        ddir = cache.dataset_dir("babyslakh")
        source_id = clip["source_id"]  # e.g. "Track00001"

        mix_dest = ddir / "extracted" / source_id / "mix.wav"
        midi_dest = ddir / "extracted" / source_id / "all_src.mid"
        if not mix_dest.exists() or not midi_dest.exists():
            tar_path = download(_TAR_URL, ddir / "babyslakh_16k.tar.gz")
            prefix = f"babyslakh_16k/{source_id}/"
            with tarfile.open(tar_path, "r:gz") as tf:
                members = [m for m in tf.getmembers() if m.name.startswith(prefix)]
                if not members:
                    raise ManualAcquisitionError(
                        f"BabySlakh track '{source_id}' not found in babyslakh_16k.tar.gz."
                    )
                mix_dest.parent.mkdir(parents=True, exist_ok=True)
                for m in members:
                    name = Path(m.name).name
                    if name in ("mix.wav", "all_src.mid"):
                        f = tf.extractfile(m)
                        if f:
                            (mix_dest.parent / name).write_bytes(f.read())

        return ResolvedClip(
            audio_path=str(mix_dest),
            reference_midi_path=str(midi_dest),
        )


def load_babyslakh_notes(midi_path: str) -> list[dict[str, Any]]:
    return parse_babyslakh_midi(Path(midi_path).read_bytes())
