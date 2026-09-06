"""Exact-Version Score ↔ performance alignment through Parangonar.

The normalized relation contract already lives in ``domain.score_performance_alignment``.
This adapter only executes the admitted matcher against explicitly supplied MusicXML
and performance-MIDI bytes. It deliberately does not resolve a Work's "latest" MIDI
or Score; #613 owns that representation-authority decision.
"""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
from pathlib import Path
from uuid import UUID

from domain.score_performance_alignment import (
    AlignmentInputRole,
    AlignmentInputVersion,
    AlignmentSufficiencyPolicy,
    ScorePerformanceAlignment,
    normalize_parangonar_alignment,
)

PARANGONAR_VERSION = "3.3.3"
PARTITURA_VERSION = "1.9.0"
MATCHER = "DualDTWNoteMatcher"
_OUTPUT_PREFIX = "LISTENCLOSER_PARANGONAR_JSON="
_DEFAULT_TIMEOUT_SECONDS = 10 * 60


class ParangonarAlignmentEngine:
    """Run the admitted symbolic matcher in a separately provisioned runtime."""

    def __init__(
        self,
        *,
        runtime_python: str | None = None,
        timeout_seconds: float = _DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        if timeout_seconds <= 0:
            raise ValueError("Parangonar timeout must be positive")
        self._runtime_python = runtime_python or os.getenv("PARANGONAR_RUNTIME_PYTHON")
        self._timeout_seconds = timeout_seconds

    def _runtime(self) -> Path:
        if not self._runtime_python:
            raise RuntimeError(
                "Parangonar requires PARANGONAR_RUNTIME_PYTHON pointing to the "
                "pinned 3.3.3 runtime"
            )
        runtime_python = Path(self._runtime_python)
        if not runtime_python.is_file():
            raise RuntimeError(f"Parangonar runtime Python not found: {runtime_python}")
        return runtime_python

    def align(
        self,
        *,
        score_musicxml: bytes,
        performance_midi: bytes,
        score_version_id: UUID,
        performance_version_id: UUID,
        sufficiency_policy: AlignmentSufficiencyPolicy,
    ) -> ScorePerformanceAlignment:
        """Align exact immutable inputs without guessing representation authority."""

        if not score_musicxml.strip():
            raise ValueError("Parangonar requires non-empty MusicXML bytes")
        if len(performance_midi) < 14 or not performance_midi.startswith(b"MThd"):
            raise ValueError("Parangonar requires a valid MIDI header")
        if score_version_id == performance_version_id:
            raise ValueError("score and performance must be distinct immutable Versions")

        runtime_python = self._runtime()
        runner = Path(__file__).with_name("_parangonar_runner.py")
        with tempfile.TemporaryDirectory(prefix="listencloser-parangonar-") as tmp:
            root = Path(tmp)
            score_path = root / "score.musicxml"
            performance_path = root / "performance.mid"
            score_path.write_bytes(score_musicxml)
            performance_path.write_bytes(performance_midi)
            command = [
                str(runtime_python),
                str(runner),
                str(score_path),
                str(performance_path),
            ]
            env = os.environ.copy()
            env["PYTHONNOUSERSITE"] = "1"
            env["MPLBACKEND"] = "Agg"
            try:
                completed = subprocess.run(
                    command,
                    capture_output=True,
                    text=True,
                    env=env,
                    timeout=self._timeout_seconds,
                    check=False,
                )
            except subprocess.TimeoutExpired as exc:
                raise RuntimeError("Parangonar alignment timed out") from exc

        if completed.returncode != 0:
            stderr_tail = (completed.stderr or "")[-1500:]
            raise RuntimeError(
                "Parangonar isolated runtime failed"
                + (f": {stderr_tail}" if stderr_tail else "")
            )
        payload = _parse_runner_output(completed.stdout)
        _validate_runtime_identity(payload)

        score_events = _event_map(payload, "score_events")
        performance_events = _event_map(payload, "performance_events")
        return normalize_parangonar_alignment(
            score_input=AlignmentInputVersion(
                version_id=score_version_id,
                role=AlignmentInputRole.written_score,
            ),
            performance_input=AlignmentInputVersion(
                version_id=performance_version_id,
                role=AlignmentInputRole.performed_midi,
            ),
            raw_alignment=payload.get("alignment"),
            package_version=PARANGONAR_VERSION,
            matcher=MATCHER,
            parameters=dict(payload.get("parameters") or {}),
            score_event_ids=set(score_events),
            performance_event_ids=set(performance_events),
            score_onset_beat_by_id=score_events,
            performance_onset_seconds_by_id=performance_events,
            sufficiency_policy=sufficiency_policy,
            matcher_failure=_optional_string(payload.get("failure")),
        )


def _parse_runner_output(stdout: str) -> dict[str, object]:
    for line in reversed(stdout.splitlines()):
        if not line.startswith(_OUTPUT_PREFIX):
            continue
        try:
            payload = json.loads(line[len(_OUTPUT_PREFIX) :])
        except json.JSONDecodeError as exc:
            raise RuntimeError("Parangonar runner emitted invalid JSON") from exc
        if not isinstance(payload, dict):
            raise RuntimeError("Parangonar runner payload must be an object")
        return payload
    raise RuntimeError("Parangonar runner completed without a result payload")


def _validate_runtime_identity(payload: dict[str, object]) -> None:
    if payload.get("parangonar_version") != PARANGONAR_VERSION:
        raise RuntimeError("Parangonar runner used an unexpected package version")
    if payload.get("partitura_version") != PARTITURA_VERSION:
        raise RuntimeError("Parangonar runner used an unexpected Partitura version")
    if payload.get("matcher") != MATCHER:
        raise RuntimeError("Parangonar runner used an unexpected matcher")


def _event_map(payload: dict[str, object], key: str) -> dict[str, float]:
    raw_events = payload.get(key)
    if not isinstance(raw_events, list):
        raise RuntimeError(f"Parangonar runner {key} must be a list")
    events: dict[str, float] = {}
    for raw in raw_events:
        if not isinstance(raw, dict) or "id" not in raw or "onset" not in raw:
            raise RuntimeError(f"Parangonar runner emitted a malformed {key} event")
        event_id = str(raw["id"])
        if event_id in events:
            raise RuntimeError(f"Parangonar runner emitted duplicate {key} event ids")
        events[event_id] = float(raw["onset"])
    return events


def _optional_string(value: object) -> str | None:
    return None if value is None else str(value)
