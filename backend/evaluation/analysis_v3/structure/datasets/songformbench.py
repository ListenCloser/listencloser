"""Build hello-ai Structure manifests from SongFormBench annotations.

Audio is never downloaded by this helper. It references only audio that has already
been legitimately materialized locally and records whether that audio is original,
mel-reconstructed, or of unknown local provenance.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

_AUDIO_EXTENSIONS = (".wav", ".flac", ".mp3", ".m4a", ".ogg")
_AUDIO_PROVENANCE = ("original", "mel_reconstruction", "local_unknown")


def _sections_from_points(
    points: list[tuple[float, str]],
    source: str | Path,
) -> list[dict[str, Any]]:
    if len(points) < 2:
        raise ValueError(f"{source}: annotation needs at least one section and an end marker")
    if points[-1][1] != "end":
        raise ValueError(f"{source}: final annotation row must use the 'end' marker")

    for previous, current in zip(points, points[1:], strict=False):
        if current[0] <= previous[0]:
            raise ValueError(f"{source}: timestamps must be strictly increasing")

    sections = []
    for (start, label), (end, _) in zip(points, points[1:], strict=False):
        if label != "end":
            sections.append({"start": start, "end": end, "label": label})
    return sections


def parse_msa_annotation(path: str | Path) -> list[dict[str, Any]]:
    """Parse ``timestamp label`` rows into contiguous section intervals."""
    points: list[tuple[float, str]] = []
    for line_number, raw_line in enumerate(Path(path).read_text().splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue
        parts = line.split(maxsplit=1)
        if len(parts) != 2:
            raise ValueError(f"{path}:{line_number}: expected '<seconds> <label>'")
        try:
            timestamp = float(parts[0])
        except ValueError as exc:
            raise ValueError(f"{path}:{line_number}: invalid timestamp {parts[0]!r}") from exc
        points.append((timestamp, parts[1].strip().lower()))

    return _sections_from_points(points, path)


def _resolve_audio(audio_dir: Path, annotation_path: Path, annotation_dir: Path) -> Path | None:
    relative = annotation_path.relative_to(annotation_dir).with_suffix("")
    for extension in _AUDIO_EXTENSIONS:
        candidate = (audio_dir / relative).with_suffix(extension)
        if candidate.is_file():
            return candidate

    matches = [
        candidate
        for candidate in audio_dir.rglob(f"{annotation_path.stem}.*")
        if candidate.suffix.lower() in _AUDIO_EXTENSIONS and candidate.is_file()
    ]
    if len(matches) > 1:
        raise ValueError(
            f"Ambiguous audio for {annotation_path.name}: "
            + ", ".join(str(match) for match in matches)
        )
    return matches[0] if matches else None


def _write_manifest(
    clips: list[dict[str, Any]],
    output_path: str | Path,
    *,
    name: str,
    description: str,
) -> str:
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps({"name": name, "description": description, "clips": clips}, indent=2) + "\n"
    )
    return str(destination)


def build_songformbench_manifest(
    annotation_dir: str | Path,
    audio_dir: str | Path,
    output_path: str | Path,
    *,
    dataset_name: str = "SongFormBench",
    split: str = "test",
    audio_provenance: str = "local_unknown",
) -> dict[str, Any]:
    """Create a manifest from MSA text files with locally available audio."""
    if audio_provenance not in _AUDIO_PROVENANCE:
        raise ValueError(f"Unknown audio provenance: {audio_provenance}")

    annotation_root = Path(annotation_dir).resolve()
    audio_root = Path(audio_dir).resolve()
    annotations = sorted(annotation_root.rglob("*.txt"))
    if not annotations:
        raise ValueError(f"No .txt annotations found under {annotation_root}")

    clips: list[dict[str, Any]] = []
    missing_audio: list[str] = []
    for annotation_path in annotations:
        sections = parse_msa_annotation(annotation_path)
        audio_path = _resolve_audio(audio_root, annotation_path, annotation_root)
        relative_id = annotation_path.relative_to(annotation_root).with_suffix("").as_posix()
        if audio_path is None:
            missing_audio.append(relative_id)
            continue
        clips.append(
            {
                "id": f"songformbench-{relative_id.replace('/', '-')}",
                "audio": str(audio_path),
                "category": "full_mix",
                "dataset": dataset_name,
                "split": split,
                "source_id": relative_id,
                "license": "SongFormBench metadata/annotations: CC BY 4.0",
                "audio_provenance": audio_provenance,
                "metrics": ["structure"],
                "reference": {"sections": sections},
            }
        )

    manifest_path = _write_manifest(
        clips,
        output_path,
        name=f"{dataset_name}-{split}",
        description=(
            "Structure boundary evaluation manifest generated from SongFormBench-style "
            "expert annotations. Audio is local-only and is not redistributed."
        ),
    )
    return {
        "manifest": manifest_path,
        "annotation_count": len(annotations),
        "materialized_clip_count": len(clips),
        "missing_audio_count": len(missing_audio),
        "missing_audio_source_ids": missing_audio,
        "audio_provenance": audio_provenance,
    }


def _index_sections(entry: dict[str, Any], source: str) -> list[dict[str, Any]]:
    raw_labels = entry.get("labels", [])
    points: list[tuple[float, str]] = []
    for index, label in enumerate(raw_labels):
        if not isinstance(label, dict) or "start" not in label or "label" not in label:
            raise ValueError(f"{source}: labels[{index}] must contain start and label")
        points.append((float(label["start"]), str(label["label"]).strip().lower()))
    return _sections_from_points(points, source)


def build_songformbench_index_manifest(
    index_path: str | Path,
    dataset_root: str | Path,
    output_path: str | Path,
    *,
    audio_provenance: str = "local_unknown",
    subsets: tuple[str, ...] = (),
) -> dict[str, Any]:
    """Build from SongFormBench's canonical ``data/SongFormBench.jsonl`` manual index."""
    if audio_provenance not in _AUDIO_PROVENANCE:
        raise ValueError(f"Unknown audio provenance: {audio_provenance}")

    root = Path(dataset_root).resolve()
    entries = [
        json.loads(line)
        for line in Path(index_path).read_text().splitlines()
        if line.strip()
    ]
    if not entries:
        raise ValueError(f"No SongFormBench entries found in {index_path}")

    clips: list[dict[str, Any]] = []
    missing_audio: list[dict[str, str]] = []
    selected_entries = 0
    for entry in entries:
        source_id = str(entry.get("id", "")).strip()
        if not source_id:
            raise ValueError(f"{index_path}: entry missing id")
        subset = str(entry.get("subset", "unknown")).strip() or "unknown"
        if subsets and subset not in subsets:
            continue
        selected_entries += 1

        audio_rel = str(entry.get("audio_path", "")).strip()
        if not audio_rel:
            raise ValueError(f"{source_id}: entry missing audio_path")
        audio_path = root / audio_rel
        if not audio_path.is_file():
            missing_audio.append(
                {
                    "source_id": source_id,
                    "expected_audio": str(audio_path),
                    "mel_path": str(root / str(entry.get("mel_path", ""))),
                }
            )
            continue

        clips.append(
            {
                "id": f"songformbench-{source_id}",
                "audio": str(audio_path),
                "category": "full_mix",
                "dataset": f"SongFormBench-{subset}",
                "split": "test",
                "source_id": source_id,
                "license": "SongFormBench metadata/annotations: CC BY 4.0",
                "audio_provenance": audio_provenance,
                "metrics": ["structure"],
                "reference": {"sections": _index_sections(entry, source_id)},
            }
        )

    subset_suffix = "-" + "-".join(subsets) if subsets else ""
    manifest_path = _write_manifest(
        clips,
        output_path,
        name=f"SongFormBench-test{subset_suffix}",
        description=(
            "Structure boundary evaluation manifest generated from the canonical "
            "SongFormBench.jsonl index. Audio provenance is explicit and audio is not "
            "downloaded or redistributed by hello-ai."
        ),
    )
    return {
        "manifest": manifest_path,
        "index_entry_count": len(entries),
        "selected_entry_count": selected_entries,
        "materialized_clip_count": len(clips),
        "missing_audio_count": len(missing_audio),
        "missing_audio": missing_audio,
        "audio_provenance": audio_provenance,
        "subsets": list(subsets),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a SongFormBench Structure manifest")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--index", help="Canonical data/SongFormBench.jsonl")
    source.add_argument("--annotation-dir", help="Directory of timestamp/label text files")
    parser.add_argument("--audio-dir", required=True, help="Local dataset/audio root")
    parser.add_argument("--output", required=True)
    parser.add_argument("--dataset-name", default="SongFormBench")
    parser.add_argument("--split", default="test")
    parser.add_argument("--subset", action="append", default=[])
    parser.add_argument("--audio-provenance", choices=_AUDIO_PROVENANCE, default="local_unknown")
    args = parser.parse_args()

    if args.index:
        summary = build_songformbench_index_manifest(
            args.index,
            args.audio_dir,
            args.output,
            audio_provenance=args.audio_provenance,
            subsets=tuple(args.subset),
        )
    else:
        summary = build_songformbench_manifest(
            args.annotation_dir,
            args.audio_dir,
            args.output,
            dataset_name=args.dataset_name,
            split=args.split,
            audio_provenance=args.audio_provenance,
        )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
