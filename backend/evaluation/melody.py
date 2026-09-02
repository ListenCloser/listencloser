"""Focused evaluation contract for symbolic melody extraction.

This module intentionally does not own dataset download, model selection, or
production routing. It exists to make #1026 comparisons fail closed unless the
historical POP909 holdout can be identified exactly, and to keep note-level
metrics/failure accounting identical across baseline and challenger runners.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from statistics import fmean

_POP909_DATASET = "POP909"
_POP909_TEST_SPLIT = "test"
_POP909_TEST_COUNT = 91
_POP909_SPLIT_SEED = 42
_SONG_ID_RE = re.compile(r"^\d{3}$")


@dataclass(frozen=True)
class MelodySplitManifest:
    """Exact dataset membership required for a leakage-safe comparison."""

    dataset: str
    split: str
    split_seed: int
    song_ids: tuple[str, ...]
    source: str
    sha256: str


@dataclass(frozen=True)
class BinaryMelodyMetrics:
    """Binary melody/non-melody metrics for one song."""

    precision: float
    recall: float
    f1: float
    reference_positive: int
    predicted_positive: int
    true_positive: int


@dataclass(frozen=True)
class MelodySongResult:
    """One song's scored result or an explicit failure/abstention."""

    song_id: str
    status: str
    metrics: BinaryMelodyMetrics | None = None
    reason: str | None = None


@dataclass(frozen=True)
class MelodyAggregate:
    """Macro metrics with failures kept visible in the denominator."""

    song_count: int
    scored_count: int
    abstained_count: int
    error_count: int
    macro_precision: float
    macro_recall: float
    macro_f1: float
    failure_rate_f1_lt_0_2: float
    prediction_reference_ratio: float


def load_pop909_test_manifest(path: str | Path) -> MelodySplitManifest:
    """Load the exact historical POP909 test membership.

    A seed alone is not sufficient. The historical report says only 903 of 909
    songs were processed, so regenerating a shuffle without the exact processed
    set can silently change holdout membership and contaminate the comparison.
    """

    manifest_path = Path(path)
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))

    if payload.get("schema_version") != 1:
        raise ValueError("melody split manifest schema_version must be 1")
    if payload.get("dataset") != _POP909_DATASET:
        raise ValueError("melody split manifest must identify POP909")
    if payload.get("split") != _POP909_TEST_SPLIT:
        raise ValueError("melody split manifest must identify the test split")
    if payload.get("split_seed") != _POP909_SPLIT_SEED:
        raise ValueError("melody split manifest must preserve historical split_seed=42")

    raw_song_ids = payload.get("song_ids")
    if not isinstance(raw_song_ids, list):
        raise ValueError("melody split manifest must contain exact song_ids; seed-only is invalid")
    if len(raw_song_ids) != _POP909_TEST_COUNT:
        raise ValueError(
            f"POP909 historical test manifest must contain exactly {_POP909_TEST_COUNT} song_ids"
        )

    song_ids = tuple(str(song_id) for song_id in raw_song_ids)
    if len(set(song_ids)) != len(song_ids):
        raise ValueError("melody split manifest song_ids must be unique")
    invalid_ids = [song_id for song_id in song_ids if not _SONG_ID_RE.fullmatch(song_id)]
    if invalid_ids:
        raise ValueError(f"POP909 song_ids must be zero-padded three-digit strings: {invalid_ids!r}")

    source = payload.get("source")
    if not isinstance(source, str) or not source.strip():
        raise ValueError("melody split manifest must name the source of the exact membership")

    canonical = json.dumps(
        {
            "dataset": _POP909_DATASET,
            "split": _POP909_TEST_SPLIT,
            "split_seed": _POP909_SPLIT_SEED,
            "song_ids": song_ids,
            "source": source,
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")

    return MelodySplitManifest(
        dataset=_POP909_DATASET,
        split=_POP909_TEST_SPLIT,
        split_seed=_POP909_SPLIT_SEED,
        song_ids=song_ids,
        source=source,
        sha256=hashlib.sha256(canonical).hexdigest(),
    )


def score_binary_note_labels(
    reference_labels: Sequence[bool | int],
    predicted_labels: Sequence[bool | int],
) -> BinaryMelodyMetrics:
    """Score one aligned note sequence under a binary melody contract."""

    if len(reference_labels) != len(predicted_labels):
        raise ValueError("reference and predicted label sequences must have identical lengths")
    if not reference_labels:
        raise ValueError("cannot score an empty note sequence")

    reference = tuple(bool(label) for label in reference_labels)
    predicted = tuple(bool(label) for label in predicted_labels)

    reference_positive = sum(reference)
    predicted_positive = sum(predicted)
    true_positive = sum(ref and pred for ref, pred in zip(reference, predicted, strict=True))

    precision = true_positive / predicted_positive if predicted_positive else 0.0
    recall = true_positive / reference_positive if reference_positive else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0

    return BinaryMelodyMetrics(
        precision=precision,
        recall=recall,
        f1=f1,
        reference_positive=reference_positive,
        predicted_positive=predicted_positive,
        true_positive=true_positive,
    )


def aggregate_song_results(results: Sequence[MelodySongResult]) -> MelodyAggregate:
    """Aggregate per-song results without dropping abstentions or errors.

    Failed/abstained songs contribute zero to macro P/R/F1 and to the failure
    rate. This prevents an engine from looking better merely by returning no
    result on difficult songs.
    """

    if not results:
        raise ValueError("cannot aggregate an empty melody result set")

    valid_statuses = {"ok", "abstained", "error"}
    invalid_statuses = {result.status for result in results} - valid_statuses
    if invalid_statuses:
        raise ValueError(f"unknown melody result statuses: {sorted(invalid_statuses)!r}")

    for result in results:
        if result.status == "ok" and result.metrics is None:
            raise ValueError(f"scored result {result.song_id!r} is missing metrics")
        if result.status != "ok" and result.metrics is not None:
            raise ValueError(f"non-scored result {result.song_id!r} must not contain metrics")

    precisions = [result.metrics.precision if result.metrics else 0.0 for result in results]
    recalls = [result.metrics.recall if result.metrics else 0.0 for result in results]
    f1s = [result.metrics.f1 if result.metrics else 0.0 for result in results]

    reference_positive = sum(
        result.metrics.reference_positive for result in results if result.metrics is not None
    )
    predicted_positive = sum(
        result.metrics.predicted_positive for result in results if result.metrics is not None
    )

    return MelodyAggregate(
        song_count=len(results),
        scored_count=sum(result.status == "ok" for result in results),
        abstained_count=sum(result.status == "abstained" for result in results),
        error_count=sum(result.status == "error" for result in results),
        macro_precision=fmean(precisions),
        macro_recall=fmean(recalls),
        macro_f1=fmean(f1s),
        failure_rate_f1_lt_0_2=sum(f1 < 0.2 for f1 in f1s) / len(f1s),
        prediction_reference_ratio=(
            predicted_positive / reference_positive if reference_positive else 0.0
        ),
    )
