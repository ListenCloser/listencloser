"""Materialize fixed BabySlakh mixture + bass MIDI evidence for AMT scoring."""

from __future__ import annotations

import hashlib
import tarfile
from pathlib import Path, PurePosixPath
from typing import Any

from evaluation.datasets import cache
from evaluation.datasets._download import download

BABYSLAKH_TAR_URL = "https://zenodo.org/records/4603870/files/babyslakh_16k.tar.gz?download=1"
BABYSLAKH_TAR_MD5 = "311096dc2bde7d61c97e930edbfc7f78"


def _md5(path: Path) -> str:
    digest = hashlib.md5(usedforsecurity=False)
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_selected_relative_path(member_name: str, track_id: str) -> Path | None:
    member = PurePosixPath(member_name)
    prefix = PurePosixPath("babyslakh_16k") / track_id
    try:
        relative = member.relative_to(prefix)
    except ValueError:
        return None

    parts = relative.parts
    if parts in {("mix.wav",), ("metadata.yaml",)}:
        return Path(*parts)
    if len(parts) == 2 and parts[0] == "MIDI" and parts[1].endswith(".mid"):
        return Path(*parts)
    return None


def materialize_tracks(track_ids: tuple[str, ...]) -> dict[str, Path]:
    """Download BabySlakh once and extract only mix/metadata/source MIDI."""
    if not track_ids:
        raise ValueError("track_ids must be non-empty")

    dataset_dir = cache.dataset_dir("babyslakh")
    tar_path = download(BABYSLAKH_TAR_URL, dataset_dir / "babyslakh_16k.tar.gz")
    actual_md5 = _md5(tar_path)
    if actual_md5 != BABYSLAKH_TAR_MD5:
        raise ValueError(
            f"BabySlakh archive checksum mismatch: expected {BABYSLAKH_TAR_MD5}, got {actual_md5}"
        )

    output_root = dataset_dir / "bass_amt_reference"
    resolved = {track_id: output_root / track_id for track_id in track_ids}
    complete = all(
        (track_dir / "mix.wav").is_file()
        and (track_dir / "metadata.yaml").is_file()
        and (track_dir / "MIDI").is_dir()
        and any((track_dir / "MIDI").glob("*.mid"))
        for track_dir in resolved.values()
    )
    if complete:
        return resolved

    with tarfile.open(tar_path, "r:gz") as archive:
        for member in archive:
            if not member.isfile():
                continue
            for track_id, track_dir in resolved.items():
                relative = _safe_selected_relative_path(member.name, track_id)
                if relative is None:
                    continue
                source = archive.extractfile(member)
                if source is None:
                    continue
                destination = track_dir / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(source.read())
                break

    for track_id, track_dir in resolved.items():
        if not (track_dir / "mix.wav").is_file() or not (track_dir / "metadata.yaml").is_file():
            raise ValueError(f"BabySlakh track {track_id} missing mix or metadata after extraction")
        if not any((track_dir / "MIDI").glob("*.mid")):
            raise ValueError(f"BabySlakh track {track_id} has no source MIDI after extraction")
    return resolved


def _load_metadata(path: Path) -> dict[str, Any]:
    try:
        import yaml
    except ImportError as exc:  # pragma: no cover - locked backend currently includes PyYAML
        raise RuntimeError("PyYAML is required for BabySlakh bass-reference preparation") from exc

    payload = yaml.safe_load(path.read_text())
    if not isinstance(payload, dict):
        raise ValueError(f"Invalid BabySlakh metadata: {path}")
    return payload


def bass_reference_midis(track_dir: Path) -> list[Path]:
    """Return aligned source MIDI files whose metadata identifies a bass class."""
    metadata = _load_metadata(track_dir / "metadata.yaml")
    source_metadata = metadata.get("stems")
    if not isinstance(source_metadata, dict):
        raise ValueError(f"BabySlakh metadata has no stems mapping: {track_dir}")

    paths: list[Path] = []
    for source_id, raw_info in sorted(source_metadata.items()):
        if not isinstance(raw_info, dict):
            continue
        instrument_class = str(raw_info.get("inst_class") or "").strip().lower()
        if "bass" not in instrument_class or bool(raw_info.get("is_drum")):
            continue
        # The released BabySlakh archive is file-authoritative for aligned MIDI
        # existence: some metadata marks midi_saved false while distributing the
        # corresponding source MIDI. The archive checksum guards identity.
        midi_path = track_dir / "MIDI" / f"{source_id}.mid"
        if midi_path.is_file():
            paths.append(midi_path)
    return paths
