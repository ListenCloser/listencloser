"""Build an independent Salsa pulse manifest from the public Zenodo fragments.

The Salsa Dataset was published independently of Beat This and is not present in
Beat This's published training-corpus list. It contains expert-refined beat
annotations for 124 salsa recordings, a useful rhythmically difficult domain
probe beyond the checkpoint-associated Candombe validation result.

This helper intentionally fails closed on fragment alignment. The Zenodo record
contains downloadable audio *fragments* while the paper describes full-song
expert beat annotations. We only score a fragment when the published annotation
timeline itself fits the fragment (or an explicit upstream fragment offset is
present in metadata). We never guess an excerpt offset or silently truncate a
full-song annotation to make it fit.
"""

from __future__ import annotations

import csv
import json
import re
from pathlib import Path
from typing import Any

import numpy as np
import soundfile as sf

DATASET = "salsa_zenodo_v1"
DATASET_SOURCE = "https://zenodo.org/records/13120822"
DATASET_DOI = "10.5281/zenodo.13120822"
DATASET_VERSION = "v1"
DATASET_PUBLISHED = "2024-07-29"
DATASET_LICENSE = "CC BY (Zenodo/OpenAIRE metadata)"
AUDIO_ARCHIVE_MD5 = "4e3936244b230fa9855e3b42d53201d1"
ANNOTATION_ARCHIVE_MD5 = "e6b4457a6ce6e77dbeb1f320599e481e"
METADATA_MD5 = "7c556b983e9b3fde22e6404fd0ac1578"
PAPER_DOI = "10.5334/tismir.183"
RIGHTS_NOTE = (
    "This evaluator uses only audio_fragments.zip distributed by the Zenodo record. "
    "The record is indexed as CC BY by OpenAIRE; the paper separately states that "
    "additional full-length WAV material is available on request for fair nonprofit research. "
    "No audio is committed or redistributed by hello-ai."
)

_AUDIO_SUFFIXES = {".wav", ".flac", ".mp3", ".ogg", ".m4a"}
_ID_RE = re.compile(r"(?<!\d)(\d{1,6})(?!\d)")
_OFFSET_FIELDS_SECONDS = (
    "fragment_start_seconds",
    "fragment start seconds",
    "start_seconds",
    "start seconds",
)
_OFFSET_FIELDS_MS = (
    "fragment_start_ms",
    "fragment start ms",
    "start_ms",
    "start ms",
)


def parse_salsa_beats(annotation_path: str | Path) -> list[float]:
    """Parse one Salsa annotation file whose published unit is milliseconds."""
    values: list[float] = []
    with open(annotation_path, encoding="utf-8-sig") as handle:
        for line_number, raw_line in enumerate(handle, start=1):
            line = raw_line.strip()
            if not line:
                continue
            token = line.replace(",", ".").split()[0]
            try:
                milliseconds = float(token)
            except ValueError as exc:
                raise ValueError(
                    f"Malformed Salsa beat at {annotation_path}:{line_number}: {line!r}"
                ) from exc
            if not np.isfinite(milliseconds) or milliseconds < 0:
                raise ValueError(
                    f"Invalid Salsa beat at {annotation_path}:{line_number}: {milliseconds}"
                )
            values.append(milliseconds / 1000.0)

    if len(values) < 2:
        raise ValueError(f"Need at least two Salsa beats: {annotation_path}")
    if any(later <= earlier for earlier, later in zip(values, values[1:], strict=False)):
        raise ValueError(f"Salsa beat times are not strictly increasing: {annotation_path}")
    return values


def _numeric_id(path: Path) -> str | None:
    """Extract the song id from a dataset filename without depending on folder names."""
    matches = _ID_RE.findall(path.stem)
    if not matches:
        return None
    return str(int(matches[-1]))


def _index_by_id(paths: list[Path], *, kind: str) -> dict[str, Path]:
    indexed: dict[str, Path] = {}
    for path in sorted(paths):
        song_id = _numeric_id(path)
        if song_id is None:
            continue
        if song_id in indexed:
            raise ValueError(
                f"Ambiguous Salsa {kind} id {song_id}: {indexed[song_id]} and {path}"
            )
        indexed[song_id] = path
    return indexed


def _normalize_row(row: dict[str, str]) -> dict[str, str]:
    return {str(key).strip().lower(): str(value).strip() for key, value in row.items() if key}


def _read_metadata(metadata_path: str | Path) -> dict[str, dict[str, str]]:
    with open(metadata_path, newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            raise ValueError(f"Salsa metadata has no header: {metadata_path}")
        rows = [_normalize_row(row) for row in reader]

    id_candidates = ("song id", "song_id", "songid", "id")
    id_field = next((field for field in id_candidates if any(field in row for row in rows)), None)
    if id_field is None:
        raise ValueError(
            "Could not identify Salsa song-id column; "
            f"metadata fields={reader.fieldnames!r}"
        )

    result: dict[str, dict[str, str]] = {}
    for row in rows:
        raw_id = row.get(id_field, "")
        if not raw_id:
            continue
        try:
            song_id = str(int(float(raw_id)))
        except ValueError as exc:
            raise ValueError(f"Invalid Salsa song id: {raw_id!r}") from exc
        if song_id in result:
            raise ValueError(f"Duplicate Salsa metadata id: {song_id}")
        result[song_id] = row
    return result


def _explicit_fragment_offset_seconds(row: dict[str, str]) -> float | None:
    for field in _OFFSET_FIELDS_SECONDS:
        value = row.get(field)
        if value:
            return float(value)
    for field in _OFFSET_FIELDS_MS:
        value = row.get(field)
        if value:
            return float(value) / 1000.0
    return None


def _align_reference_to_fragment(
    beats: list[float],
    *,
    duration_seconds: float,
    metadata_row: dict[str, str],
    tolerance_seconds: float = 0.25,
) -> tuple[list[float], dict[str, Any]]:
    """Return fragment-local beats only when alignment is explicitly defensible."""
    if duration_seconds <= 0:
        raise ValueError(f"Invalid Salsa fragment duration: {duration_seconds}")

    explicit_offset = _explicit_fragment_offset_seconds(metadata_row)
    if explicit_offset is not None:
        end = explicit_offset + duration_seconds
        local = [beat - explicit_offset for beat in beats if explicit_offset <= beat <= end]
        if len(local) < 2:
            raise ValueError(
                "Explicit Salsa fragment offset yielded fewer than two reference beats: "
                f"offset={explicit_offset}, duration={duration_seconds}, "
                f"annotation_span=({beats[0]}, {beats[-1]})"
            )
        return local, {
            "fragment_alignment": "explicit_metadata_offset",
            "fragment_offset_seconds": explicit_offset,
        }

    # A zero offset is accepted only if the *entire* published annotation timeline
    # fits the fragment. We do not infer that a short fragment starts at t=0 merely
    # because early beats happen to fall inside it.
    if beats[-1] <= duration_seconds + tolerance_seconds:
        return beats, {
            "fragment_alignment": "annotation_timeline_fits_fragment",
            "fragment_offset_seconds": 0.0,
        }

    raise ValueError(
        "Salsa fragment alignment is not established by upstream metadata: "
        f"fragment_duration={duration_seconds:.3f}s, "
        f"annotation_span=({beats[0]:.3f}s, {beats[-1]:.3f}s). "
        "Refusing to truncate or guess a fragment offset."
    )


def build_salsa_manifest(
    audio_root: str | Path,
    annotation_root: str | Path,
    metadata_path: str | Path,
    output_path: str | Path,
) -> dict[str, Any]:
    """Build an all-available-fragments independent beat-evaluation manifest."""
    audio_paths = [
        path
        for path in Path(audio_root).rglob("*")
        if path.is_file() and path.suffix.lower() in _AUDIO_SUFFIXES
    ]
    annotation_paths = [path for path in Path(annotation_root).rglob("*.txt") if path.is_file()]
    audios = _index_by_id(audio_paths, kind="audio")
    annotations = _index_by_id(annotation_paths, kind="annotation")
    metadata = _read_metadata(metadata_path)

    shared_ids = sorted(set(audios) & set(annotations) & set(metadata), key=int)
    if not shared_ids:
        raise ValueError(
            "No Salsa fragment/annotation/metadata ids could be joined. "
            f"audio_ids={sorted(audios)[:10]}, annotation_ids={sorted(annotations)[:10]}, "
            f"metadata_ids={sorted(metadata)[:10]}"
        )

    clips: list[dict[str, Any]] = []
    for song_id in shared_ids:
        audio_path = audios[song_id]
        annotation_path = annotations[song_id]
        info = sf.info(str(audio_path))
        duration = float(info.duration)
        full_beats = parse_salsa_beats(annotation_path)
        reference_beats, alignment = _align_reference_to_fragment(
            full_beats,
            duration_seconds=duration,
            metadata_row=metadata[song_id],
        )
        intervals = np.diff(np.asarray(reference_beats, dtype=float))
        reference_bpm = float(60.0 / np.median(intervals[intervals > 0]))
        clips.append(
            {
                "id": f"salsa_{song_id}",
                "audio_path": str(audio_path),
                "audio_available": True,
                "dataset": DATASET,
                "source_dataset": "salsa_dataset",
                "reference_beats": reference_beats,
                "reference_downbeats": None,
                "reference_beat_positions": None,
                "reference_bpm": reference_bpm,
                "reference_bpm_method": "median_reference_interbeat_interval",
                "reference_meter_numerator": None,
                "reference_meter_denominator": None,
                "audio_duration_seconds": round(duration, 6),
                "annotation_source": DATASET_SOURCE,
                "annotation_version": DATASET_VERSION,
                "annotation_license": DATASET_LICENSE,
                "audio_source": DATASET_SOURCE,
                "audio_license": DATASET_LICENSE,
                **alignment,
            }
        )

    manifest: dict[str, Any] = {
        "name": "salsa_zenodo_v1_independent_fragments",
        "description": (
            "Expert-refined beat annotations paired only with public Zenodo Salsa audio "
            "fragments whose timeline alignment can be established without guessing."
        ),
        "dataset": DATASET,
        "source_dataset": "salsa_dataset",
        "dataset_doi": DATASET_DOI,
        "paper_doi": PAPER_DOI,
        "dataset_version": DATASET_VERSION,
        "dataset_published": DATASET_PUBLISHED,
        "dataset_license": DATASET_LICENSE,
        "audio_archive_md5": AUDIO_ARCHIVE_MD5,
        "annotation_archive_md5": ANNOTATION_ARCHIVE_MD5,
        "metadata_md5": METADATA_MD5,
        "rights_note": RIGHTS_NOTE,
        "audio_redistributed": False,
        "selection": "all fragment/annotation/metadata ids with defensible alignment",
        "clips": clips,
    }

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"Built Salsa manifest with {len(clips)} scored fragments: {output}")
    return manifest


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Build independent Salsa pulse manifest")
    parser.add_argument("audio_root")
    parser.add_argument("annotation_root")
    parser.add_argument("metadata_path")
    parser.add_argument("output_path")
    args = parser.parse_args()
    build_salsa_manifest(
        args.audio_root,
        args.annotation_root,
        args.metadata_path,
        args.output_path,
    )
