"""Prepare BabySlakh references for the source-separation downstream bakeoff.

BabySlakh stores isolated source audio plus the exact per-source MIDI used to
synthesize it. This helper groups those sources into the four HTDemucs target
families (vocals/drums/bass/other), writes deterministic reference submixes, and
emits one manifest that can drive both objective SI-SDR and downstream AMT
comparisons.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
import soundfile as sf

TARGET_STEMS = ("vocals", "drums", "bass", "other")


def _load_metadata(path: Path) -> dict[str, Any]:
    try:
        import yaml
    except ImportError as exc:  # pragma: no cover - benchmark preparation guard
        raise RuntimeError(
            "BabySlakh manifest preparation requires PyYAML. "
            "Run this benchmark helper with `uv run --with pyyaml ...`."
        ) from exc

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


def _source_audio_path(track_dir: Path, source_id: str) -> Path | None:
    for suffix in (".wav", ".flac"):
        path = track_dir / "stems" / f"{source_id}{suffix}"
        if path.is_file():
            return path
    return None


def _mix_reference_sources(paths: list[Path], output_path: Path) -> None:
    if not paths:
        raise ValueError("Cannot build an empty reference submix")

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
            raise ValueError(f"Mismatched BabySlakh sample rates in {paths[0].parent}")
        audio = np.asarray(audio, dtype=np.float64)
        loaded.append(audio)
        max_samples = max(max_samples, len(audio))

    mixed = np.zeros(max_samples, dtype=np.float64)
    for audio in loaded:
        mixed[: len(audio)] += audio

    if sample_rate is None:
        raise ValueError("Cannot determine sample rate for empty reference submix")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(
        output_path,
        mixed.astype(np.float32),
        sample_rate,
        format="WAV",
        subtype="FLOAT",
    )


def _manifest_path(root: Path, path: Path, env_var: str) -> str:
    relative = path.relative_to(root).as_posix()
    return f"${{{env_var}}}/{relative}"


def build_babyslakh_manifest(
    dataset_root: Path,
    *,
    output_manifest: Path,
    limit: int = 20,
    env_var: str = "BABYSLAKH_ROOT",
) -> dict[str, Any]:
    """Build grouped references and a deterministic BabySlakh manifest."""
    dataset_root = dataset_root.resolve()
    reference_root = dataset_root / ".hello_ai_reference_4stems"
    entries: list[dict[str, Any]] = []

    track_dirs = sorted(
        path
        for path in dataset_root.rglob("Track*")
        if path.is_dir() and (path / "metadata.yaml").is_file()
    )
    for track_dir in track_dirs:
        mix_candidates = (track_dir / "mix.wav", track_dir / "mix.flac")
        mix_path = next((path for path in mix_candidates if path.is_file()), None)
        if mix_path is None:
            continue

        metadata = _load_metadata(track_dir / "metadata.yaml")
        source_metadata = metadata.get("stems")
        if not isinstance(source_metadata, dict):
            continue

        grouped_audio: dict[str, list[Path]] = {name: [] for name in TARGET_STEMS}
        grouped_midi: dict[str, list[Path]] = {name: [] for name in TARGET_STEMS}
        for source_id, raw_info in sorted(source_metadata.items()):
            if not isinstance(raw_info, dict) or raw_info.get("audio_rendered") is False:
                continue
            source_audio = _source_audio_path(track_dir, str(source_id))
            if source_audio is None:
                continue

            target = _canonical_target(raw_info)
            grouped_audio[target].append(source_audio)
            source_midi = track_dir / "MIDI" / f"{source_id}.mid"
            if source_midi.is_file():
                grouped_midi[target].append(source_midi)

        reference_stems: dict[str, str] = {}
        reference_midis: dict[str, list[str]] = {}
        source_counts: dict[str, int] = {}
        for target in TARGET_STEMS:
            sources = grouped_audio[target]
            if not sources:
                continue
            output_path = reference_root / track_dir.name / f"{target}.wav"
            _mix_reference_sources(sources, output_path)
            reference_stems[target] = _manifest_path(dataset_root, output_path, env_var)
            source_counts[target] = len(sources)
            if grouped_midi[target]:
                reference_midis[target] = [
                    _manifest_path(dataset_root, path, env_var) for path in grouped_midi[target]
                ]

        if not reference_stems:
            continue

        entries.append(
            {
                "id": track_dir.name,
                "audio_path": _manifest_path(dataset_root, mix_path, env_var),
                "dataset": "babyslakh",
                "dataset_license": "CC BY 4.0",
                "reference_stems": reference_stems,
                "reference_midis": reference_midis,
                "reference_source_counts": source_counts,
            }
        )
        if len(entries) >= limit:
            break

    if not entries:
        raise ValueError(f"No valid BabySlakh tracks found under {dataset_root}")

    payload = {
        "name": "babyslakh_4stem_reference_v1",
        "description": (
            "BabySlakh mixtures with deterministic four-family reference submixes and aligned "
            "per-source MIDI references for Analysis V3 source-separation evaluation."
        ),
        "dataset": "BabySlakh",
        "dataset_source": "https://zenodo.org/records/4603870",
        "dataset_license": "CC BY 4.0",
        "selection": "lexicographically first valid tracks",
        "limit": limit,
        "path_environment_variable": env_var,
        "clips": entries,
    }
    output_manifest.parent.mkdir(parents=True, exist_ok=True)
    output_manifest.write_text(json.dumps(payload, indent=2) + "\n")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare BabySlakh separation references")
    parser.add_argument("dataset_root", type=Path)
    parser.add_argument("output_manifest", type=Path)
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--env-var", default="BABYSLAKH_ROOT")
    args = parser.parse_args()

    payload = build_babyslakh_manifest(
        args.dataset_root,
        output_manifest=args.output_manifest,
        limit=args.limit,
        env_var=args.env_var,
    )
    print(f"Prepared {len(payload['clips'])} BabySlakh tracks at {args.output_manifest}")


if __name__ == "__main__":
    main()
