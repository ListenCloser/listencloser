"""Materialize fixed BabySlakh tracks and deterministic four-family references.

Only evaluation data is written, under the configured evaluation cache. No audio
or MIDI is committed to the repository.
"""

from __future__ import annotations

import hashlib
import tarfile
from pathlib import Path, PurePosixPath
from typing import Any

import numpy as np
import soundfile as sf

from evaluation.datasets import cache
from evaluation.datasets._download import download

BABYSLAKH_TAR_URL = "https://zenodo.org/records/4603870/files/babyslakh_16k.tar.gz?download=1"
BABYSLAKH_TAR_MD5 = "311096dc2bde7d61c97e930edbfc7f78"
TARGET_STEMS = ("vocals", "drums", "bass", "other")
_AUDIO_SUFFIXES = (".wav", ".flac")


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
    if parts in {("mix.wav",), ("mix.flac",), ("metadata.yaml",)}:
        return Path(*parts)
    if (
        len(parts) == 2
        and parts[0] == "stems"
        and Path(parts[1]).suffix.lower() in _AUDIO_SUFFIXES
    ):
        return Path(*parts)
    return None


def _mix_path(track_dir: Path) -> Path | None:
    for filename in ("mix.wav", "mix.flac"):
        path = track_dir / filename
        if path.is_file():
            return path
    return None


def _source_audio_path(track_dir: Path, source_id: str) -> Path | None:
    for suffix in _AUDIO_SUFFIXES:
        path = track_dir / "stems" / f"{source_id}{suffix}"
        if path.is_file():
            return path
    return None


def _has_isolated_audio(track_dir: Path) -> bool:
    stems_dir = track_dir / "stems"
    return stems_dir.is_dir() and any(
        path.is_file() and path.suffix.lower() in _AUDIO_SUFFIXES
        for path in stems_dir.iterdir()
    )


def materialize_tracks(track_ids: tuple[str, ...]) -> dict[str, Path]:
    """Download BabySlakh once and extract only files needed for SI-SDR scoring."""
    if not track_ids:
        raise ValueError("track_ids must be non-empty")

    dataset_dir = cache.dataset_dir("babyslakh")
    tar_path = download(BABYSLAKH_TAR_URL, dataset_dir / "babyslakh_16k.tar.gz")
    actual_md5 = _md5(tar_path)
    if actual_md5 != BABYSLAKH_TAR_MD5:
        raise ValueError(
            f"BabySlakh archive checksum mismatch: expected {BABYSLAKH_TAR_MD5}, got {actual_md5}"
        )

    output_root = dataset_dir / "objective_reference"
    resolved = {track_id: output_root / track_id for track_id in track_ids}
    complete = all(
        _mix_path(track_dir) is not None
        and (track_dir / "metadata.yaml").is_file()
        and _has_isolated_audio(track_dir)
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
        if _mix_path(track_dir) is None or not (track_dir / "metadata.yaml").is_file():
            raise ValueError(f"BabySlakh track {track_id} missing mix or metadata after extraction")
        if not _has_isolated_audio(track_dir):
            raise ValueError(f"BabySlakh track {track_id} has no isolated stems after extraction")
    return resolved


def _load_metadata(path: Path) -> dict[str, Any]:
    try:
        import yaml
    except ImportError as exc:  # pragma: no cover - benchmark environment guard
        raise RuntimeError("PyYAML is required for BabySlakh reference preparation") from exc

    payload = yaml.safe_load(path.read_text())
    if not isinstance(payload, dict):
        raise ValueError(f"Invalid BabySlakh metadata: {path}")
    return payload


def _canonical_target(info: dict[str, Any]) -> str:
    if bool(info.get("is_drum")):
        return "drums"

    instrument_class = str(info.get("inst_class") or "").strip().lower()
    if "bass" in instrument_class:
        return "bass"
    if instrument_class in {"voice", "vocal", "vocals"} or "voice" in instrument_class:
        return "vocals"
    return "other"


def _mix_reference_sources(
    paths: list[Path],
    output_path: Path,
    *,
    excerpt_seconds: float,
) -> None:
    if not paths:
        raise ValueError("Cannot build an empty reference submix")
    if excerpt_seconds <= 0:
        raise ValueError("excerpt_seconds must be positive")

    loaded: list[np.ndarray] = []
    sample_rate: int | None = None
    max_samples = 0
    for path in paths:
        audio, sr = sf.read(path, dtype="float32", always_2d=False)
        if audio.ndim > 1:
            audio = audio.mean(axis=1)
        if sample_rate is None:
            sample_rate = int(sr)
        elif int(sr) != sample_rate:
            raise ValueError(f"Mismatched BabySlakh sample rates under {paths[0].parent}")
        limit = min(len(audio), int(excerpt_seconds * int(sr)))
        excerpt = np.asarray(audio[:limit], dtype=np.float64)
        loaded.append(excerpt)
        max_samples = max(max_samples, len(excerpt))

    if sample_rate is None:
        raise ValueError("Cannot determine sample rate for empty reference submix")
    mixed = np.zeros(max_samples, dtype=np.float64)
    for audio in loaded:
        mixed[: len(audio)] += audio

    output_path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(
        output_path,
        mixed.astype(np.float32),
        sample_rate,
        format="WAV",
        subtype="FLOAT",
    )


def build_reference_stems(
    track_dir: Path,
    *,
    excerpt_seconds: float,
) -> tuple[Path, dict[str, Path], dict[str, int]]:
    """Build four-family reference submixes from exact isolated BabySlakh sources."""
    metadata = _load_metadata(track_dir / "metadata.yaml")
    source_metadata = metadata.get("stems")
    if not isinstance(source_metadata, dict):
        raise ValueError(f"BabySlakh metadata has no stems mapping: {track_dir}")

    grouped: dict[str, list[Path]] = {target: [] for target in TARGET_STEMS}
    missing_audio_ids: list[str] = []
    for source_id, raw_info in sorted(source_metadata.items()):
        source_id = str(source_id)
        if not isinstance(raw_info, dict):
            continue
        # The released BabySlakh archive is file-authoritative for reference
        # existence: some metadata marks audio_rendered false while distributing
        # the corresponding isolated WAV. The archive checksum guards identity.
        source_path = _source_audio_path(track_dir, source_id)
        if source_path is None:
            missing_audio_ids.append(source_id)
            continue
        grouped[_canonical_target(raw_info)].append(source_path)

    reference_root = track_dir / ".hello_ai_reference_4stems"
    references: dict[str, Path] = {}
    counts: dict[str, int] = {}
    for target, sources in grouped.items():
        if not sources:
            continue
        output_path = reference_root / f"{target}_{excerpt_seconds:g}s.wav"
        _mix_reference_sources(sources, output_path, excerpt_seconds=excerpt_seconds)
        references[target] = output_path
        counts[target] = len(sources)

    if not references:
        extracted = sorted(
            path.name for path in (track_dir / "stems").iterdir() if path.is_file()
        )
        classes = {
            str(source_id): raw_info.get("inst_class")
            for source_id, raw_info in source_metadata.items()
            if isinstance(raw_info, dict)
        }
        raise ValueError(
            "No reference source families found for "
            f"{track_dir.name}; metadata_ids={sorted(map(str, source_metadata))}; "
            f"extracted_stems={extracted}; missing_audio_ids={missing_audio_ids}; "
            f"inst_classes={classes}"
        )
    mix_path = _mix_path(track_dir)
    if mix_path is None:
        raise ValueError(f"Missing mixture for {track_dir.name}")
    return mix_path, references, counts
