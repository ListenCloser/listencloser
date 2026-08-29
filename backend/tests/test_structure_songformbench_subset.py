"""Deterministic corpus-selection tests for SongFormBench Structure evaluation."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from evaluation.analysis_v3.structure.datasets.songformbench_subset import (
    select_songformbench_subset,
)


def _entry(source_id: str, subset: str = "CN", *, terminal_label: str = "end") -> dict:
    return {
        "id": source_id,
        "subset": subset,
        "audio_path": f"audio/{source_id}.wav",
        "mel_path": f"mels/{source_id}.npy",
        "label_path": f"labels/{source_id}.txt",
        "labels": [
            {"start": 0.0, "label": "intro"},
            {"start": 5.0, "label": terminal_label},
        ],
    }


def _write_index(path: Path, entries: list[dict]) -> bytes:
    raw = ("\n".join(json.dumps(entry) for entry in entries) + "\n").encode()
    path.write_bytes(raw)
    return raw


def test_subset_selection_is_source_id_deterministic_and_pins_index_hash(tmp_path: Path) -> None:
    index = tmp_path / "SongFormBench.jsonl"
    raw = _write_index(
        index,
        [
            _entry("BC_z"),
            _entry("BHX_a", subset="HarmonixSet"),
            _entry("BC_a"),
            _entry("BC_m"),
        ],
    )
    filtered = tmp_path / "selected.jsonl"
    provenance_path = tmp_path / "selection.json"

    result = select_songformbench_subset(
        index,
        filtered,
        provenance_path,
        subset="CN",
        count=2,
        upstream_revision="example-revision",
    )

    assert result["selection_policy"] == "lexicographic_source_id_v1"
    assert result["source_subset"] == "CN"
    assert result["selected_source_ids"] == ["BC_a", "BC_m"]
    assert result["canonical_index_sha256"] == hashlib.sha256(raw).hexdigest()
    assert result["upstream_revision"] == "example-revision"
    assert [row["source_id"] for row in result["rows"]] == ["BC_a", "BC_m"]
    assert result["rows"][0]["annotation_end_seconds"] == 5.0

    selected_entries = [json.loads(line) for line in filtered.read_text().splitlines()]
    assert [entry["id"] for entry in selected_entries] == ["BC_a", "BC_m"]
    assert json.loads(provenance_path.read_text()) == result


def test_subset_selection_does_not_depend_on_canonical_index_row_order(tmp_path: Path) -> None:
    first = tmp_path / "first.jsonl"
    second = tmp_path / "second.jsonl"
    entries = [_entry("BC_c"), _entry("BC_a"), _entry("BC_b")]
    _write_index(first, entries)
    _write_index(second, list(reversed(entries)))

    first_result = select_songformbench_subset(
        first,
        tmp_path / "first-selected.jsonl",
        tmp_path / "first-selection.json",
        count=2,
    )
    second_result = select_songformbench_subset(
        second,
        tmp_path / "second-selected.jsonl",
        tmp_path / "second-selection.json",
        count=2,
    )

    assert first_result["selected_source_ids"] == ["BC_a", "BC_b"]
    assert second_result["selected_source_ids"] == ["BC_a", "BC_b"]
    assert first_result["selection_sha256"] == second_result["selection_sha256"]
    assert first_result["canonical_index_sha256"] != second_result["canonical_index_sha256"]


def test_subset_selection_does_not_silently_map_bc_to_cn(tmp_path: Path) -> None:
    index = tmp_path / "SongFormBench.jsonl"
    _write_index(index, [_entry("BC_a")])

    with pytest.raises(ValueError, match="Requested 1 BC rows.*only 0"):
        select_songformbench_subset(
            index,
            tmp_path / "selected.jsonl",
            tmp_path / "selection.json",
            subset="BC",
            count=1,
        )


def test_subset_selection_fails_closed_on_bad_annotations_or_too_few_rows(tmp_path: Path) -> None:
    bad_index = tmp_path / "bad.jsonl"
    _write_index(bad_index, [_entry("BC_bad", terminal_label="chorus")])

    with pytest.raises(ValueError, match="final label must be 'end'"):
        select_songformbench_subset(
            bad_index,
            tmp_path / "bad-selected.jsonl",
            tmp_path / "bad-selection.json",
            count=1,
        )

    small_index = tmp_path / "small.jsonl"
    _write_index(small_index, [_entry("BC_only")])
    with pytest.raises(ValueError, match="Requested 2 CN rows"):
        select_songformbench_subset(
            small_index,
            tmp_path / "small-selected.jsonl",
            tmp_path / "small-selection.json",
            count=2,
        )
