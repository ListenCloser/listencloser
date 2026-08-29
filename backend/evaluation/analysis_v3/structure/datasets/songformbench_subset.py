"""Select a deterministic SongFormBench subset before audio materialization.

This helper never downloads or reconstructs audio. It turns the canonical upstream
index into a fixed, auditable JSONL selection whose source IDs are chosen without
looking at candidate outputs.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

_SELECTION_POLICY = "lexicographic_source_id_v1"
_DATASET = "ASLP-lab/SongFormBench"


def _annotation_end_seconds(entry: dict[str, Any], source_id: str) -> float:
    labels = entry.get("labels", [])
    if not labels:
        raise ValueError(f"{source_id}: labels must contain a terminal end marker")
    final = labels[-1]
    if not isinstance(final, dict) or "start" not in final or "label" not in final:
        raise ValueError(f"{source_id}: final label must contain start and label")
    if str(final["label"]).strip().lower() != "end":
        raise ValueError(f"{source_id}: final label must be 'end'")
    return float(final["start"])


def select_songformbench_subset(
    index_path: str | Path,
    output_index_path: str | Path,
    provenance_path: str | Path,
    *,
    subset: str = "BC",
    count: int = 8,
    upstream_revision: str | None = None,
) -> dict[str, Any]:
    """Write a fixed subset selected only by canonical source ID ordering.

    The canonical index SHA-256 plus ordered source IDs make the selection
    reproducible even when the upstream repository later moves.
    """
    if count <= 0:
        raise ValueError("count must be positive")

    source = Path(index_path)
    raw_index = source.read_bytes()
    entries = [json.loads(line) for line in raw_index.decode("utf-8").splitlines() if line.strip()]
    if not entries:
        raise ValueError(f"No SongFormBench entries found in {source}")

    candidates: list[tuple[str, dict[str, Any], float]] = []
    seen_ids: set[str] = set()
    for entry in entries:
        source_id = str(entry.get("id", "")).strip()
        if not source_id:
            raise ValueError(f"{source}: entry missing id")
        entry_subset = str(entry.get("subset", "")).strip()
        if entry_subset != subset:
            continue
        if source_id in seen_ids:
            raise ValueError(f"{source}: duplicate source id {source_id!r} in subset {subset}")
        seen_ids.add(source_id)

        audio_path = str(entry.get("audio_path", "")).strip()
        mel_path = str(entry.get("mel_path", "")).strip()
        if not audio_path:
            raise ValueError(f"{source_id}: entry missing audio_path")
        if not mel_path:
            raise ValueError(f"{source_id}: entry missing mel_path")
        candidates.append((source_id, entry, _annotation_end_seconds(entry, source_id)))

    if len(candidates) < count:
        raise ValueError(
            f"Requested {count} {subset} rows but canonical index contains only {len(candidates)}"
        )

    selected = sorted(candidates, key=lambda item: item[0])[:count]
    selected_ids = [source_id for source_id, _, _ in selected]
    selection_bytes = ("\n".join(selected_ids) + "\n").encode("utf-8")

    output_index = Path(output_index_path)
    output_index.parent.mkdir(parents=True, exist_ok=True)
    output_index.write_text(
        "\n".join(json.dumps(entry, ensure_ascii=False) for _, entry, _ in selected) + "\n"
    )

    rows = [
        {
            "source_id": source_id,
            "audio_path": str(entry["audio_path"]),
            "mel_path": str(entry["mel_path"]),
            "label_path": str(entry.get("label_path", "")),
            "annotation_end_seconds": end_seconds,
        }
        for source_id, entry, end_seconds in selected
    ]
    provenance = {
        "schema_version": 1,
        "dataset": _DATASET,
        "subset": subset,
        "selection_policy": _SELECTION_POLICY,
        "requested_count": count,
        "selected_count": len(selected),
        "upstream_revision": upstream_revision,
        "canonical_index_sha256": hashlib.sha256(raw_index).hexdigest(),
        "selection_sha256": hashlib.sha256(selection_bytes).hexdigest(),
        "selected_source_ids": selected_ids,
        "rows": rows,
    }

    destination = Path(provenance_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(provenance, indent=2, ensure_ascii=False) + "\n")
    return provenance


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Select a fixed SongFormBench subset before audio reconstruction"
    )
    parser.add_argument("--index", required=True, help="Canonical data/SongFormBench.jsonl")
    parser.add_argument("--output-index", required=True, help="Filtered JSONL consumed by the builder")
    parser.add_argument("--provenance", required=True, help="Selection/provenance JSON output")
    parser.add_argument("--subset", default="BC")
    parser.add_argument("--count", type=int, default=8)
    parser.add_argument(
        "--upstream-revision",
        help="Exact SongFormBench repository revision used to materialize the canonical index",
    )
    args = parser.parse_args()

    result = select_songformbench_subset(
        args.index,
        args.output_index,
        args.provenance,
        subset=args.subset,
        count=args.count,
        upstream_revision=args.upstream_revision,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
