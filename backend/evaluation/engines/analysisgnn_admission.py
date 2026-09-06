"""Deployment-shaped admission probe for the isolated AnalysisGNN runtime.

The probe never downloads a model. Callers must provide an exact local checkpoint,
its expected SHA-256, an exact MusicXML fixture, and an explicit artifact-terms
status. Two independent child trials are used so peak child RSS is measurable with
stdlib ``resource`` on Linux. Because the production adapter starts a fresh isolated
AnalysisGNN process per request, the second trial is a repeat/OS-cache observation,
not an in-memory warm-model measurement.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import resource
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from time import perf_counter
from typing import Callable, Literal

from engines.symbolic.analysisgnn import (
    ANALYSISGNN_DEFAULT_ARTIFACT,
    ANALYSISGNN_PACKAGE_VERSION,
    ANALYSISGNN_UPSTREAM_REVISION,
    AnalysisGNNEngine,
    PRODUCT_SCORE_TASKS,
    normalize_score_evidence,
)

ArtifactTermsStatus = Literal["unverified", "verified_permissive", "verified_restricted"]


@dataclass(frozen=True)
class AnalysisGNNAdmissionTrial:
    elapsed_seconds: float
    peak_child_rss_kib: int
    observation_count: int
    tasks: tuple[str, ...]


@dataclass(frozen=True)
class AnalysisGNNAdmissionReport:
    schema_version: int
    upstream_revision: str
    package_version: str
    upstream_default_artifact: str
    checkpoint_sha256: str
    score_sha256: str
    artifact_terms_status: ArtifactTermsStatus
    process_reuse: bool
    first_run: AnalysisGNNAdmissionTrial
    repeat_run: AnalysisGNNAdmissionTrial
    admission_ready: bool
    interpretation: str


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _run_trial(
    *,
    runtime_python: Path,
    checkpoint: Path,
    checkpoint_sha256: str,
    score: Path,
    timeout_seconds: float,
) -> AnalysisGNNAdmissionTrial:
    """Run one fresh isolated inference and measure wall time + child peak RSS."""

    engine = AnalysisGNNEngine(
        runtime_python=str(runtime_python),
        checkpoint_path=str(checkpoint),
        checkpoint_sha256=checkpoint_sha256,
        device="cpu",
        timeout_seconds=timeout_seconds,
    )
    score_bytes = score.read_bytes()
    started = perf_counter()
    result = engine.analyze_musicxml(score_bytes, tasks=PRODUCT_SCORE_TASKS)
    elapsed = perf_counter() - started
    evidence = normalize_score_evidence(result)
    usage = resource.getrusage(resource.RUSAGE_CHILDREN)
    return AnalysisGNNAdmissionTrial(
        elapsed_seconds=round(elapsed, 6),
        peak_child_rss_kib=int(usage.ru_maxrss),
        observation_count=len(evidence.observations),
        tasks=evidence.tasks,
    )


def _run_trial_subprocess(
    *,
    runtime_python: Path,
    checkpoint: Path,
    checkpoint_sha256: str,
    score: Path,
    timeout_seconds: float,
) -> AnalysisGNNAdmissionTrial:
    """Launch one fresh LC probe process so child-RSS accounting resets per trial."""

    command = [
        sys.executable,
        "-m",
        "evaluation.engines.analysisgnn_admission",
        "trial",
        "--runtime-python",
        str(runtime_python),
        "--checkpoint",
        str(checkpoint),
        "--expected-checkpoint-sha256",
        checkpoint_sha256,
        "--score",
        str(score),
        "--timeout-seconds",
        str(timeout_seconds),
    ]
    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=max(timeout_seconds + 30.0, timeout_seconds * 1.2),
        check=False,
    )
    if completed.returncode != 0:
        stderr_tail = (completed.stderr or "")[-2000:]
        raise RuntimeError(
            "AnalysisGNN admission trial failed"
            + (f": {stderr_tail}" if stderr_tail else "")
        )
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError("AnalysisGNN admission trial returned invalid JSON") from exc
    return AnalysisGNNAdmissionTrial(
        elapsed_seconds=float(payload["elapsed_seconds"]),
        peak_child_rss_kib=int(payload["peak_child_rss_kib"]),
        observation_count=int(payload["observation_count"]),
        tasks=tuple(payload["tasks"]),
    )


def run_admission_probe(
    *,
    runtime_python: Path,
    checkpoint: Path,
    expected_checkpoint_sha256: str,
    score: Path,
    artifact_terms_status: ArtifactTermsStatus,
    timeout_seconds: float = 600.0,
    trial_runner: Callable[..., AnalysisGNNAdmissionTrial] = _run_trial_subprocess,
) -> AnalysisGNNAdmissionReport:
    """Run two exact-asset trials and return a machine-readable admission record."""

    if timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be positive")
    if not runtime_python.is_file():
        raise ValueError(f"AnalysisGNN runtime Python not found: {runtime_python}")
    if not checkpoint.is_file():
        raise ValueError(f"AnalysisGNN checkpoint not found: {checkpoint}")
    if not score.is_file():
        raise ValueError(f"AnalysisGNN score fixture not found: {score}")

    expected = expected_checkpoint_sha256.strip().lower()
    if len(expected) != 64 or any(character not in "0123456789abcdef" for character in expected):
        raise ValueError("expected checkpoint SHA-256 must be exactly 64 hexadecimal characters")
    actual_checkpoint_sha256 = _sha256(checkpoint)
    if actual_checkpoint_sha256 != expected:
        raise ValueError("AnalysisGNN checkpoint SHA-256 does not match the pinned expectation")

    first = trial_runner(
        runtime_python=runtime_python,
        checkpoint=checkpoint,
        checkpoint_sha256=expected,
        score=score,
        timeout_seconds=timeout_seconds,
    )
    repeat = trial_runner(
        runtime_python=runtime_python,
        checkpoint=checkpoint,
        checkpoint_sha256=expected,
        score=score,
        timeout_seconds=timeout_seconds,
    )
    if first.observation_count <= 0 or repeat.observation_count <= 0:
        raise RuntimeError("AnalysisGNN admission probe produced empty bounded evidence")

    ready = artifact_terms_status == "verified_permissive"
    return AnalysisGNNAdmissionReport(
        schema_version=1,
        upstream_revision=ANALYSISGNN_UPSTREAM_REVISION,
        package_version=ANALYSISGNN_PACKAGE_VERSION,
        upstream_default_artifact=ANALYSISGNN_DEFAULT_ARTIFACT,
        checkpoint_sha256=actual_checkpoint_sha256,
        score_sha256=_sha256(score),
        artifact_terms_status=artifact_terms_status,
        process_reuse=False,
        first_run=first,
        repeat_run=repeat,
        admission_ready=ready,
        interpretation=(
            "Each trial launches a fresh isolated AnalysisGNN process, matching the current "
            "ListenCloser adapter boundary. The repeat run may benefit from OS/filesystem cache "
            "but is not an in-memory warm-model measurement. Admission remains false unless the "
            "exact checkpoint terms are explicitly verified permissive."
        ),
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Probe the pinned AnalysisGNN runtime")
    subparsers = parser.add_subparsers(dest="command", required=True)

    def add_common(target: argparse.ArgumentParser) -> None:
        target.add_argument("--runtime-python", type=Path, required=True)
        target.add_argument("--checkpoint", type=Path, required=True)
        target.add_argument("--expected-checkpoint-sha256", required=True)
        target.add_argument("--score", type=Path, required=True)
        target.add_argument("--timeout-seconds", type=float, default=600.0)

    trial = subparsers.add_parser("trial", help="run one fresh measured inference")
    add_common(trial)

    probe = subparsers.add_parser("probe", help="run first/repeat trials and emit admission JSON")
    add_common(probe)
    probe.add_argument(
        "--artifact-terms-status",
        choices=("unverified", "verified_permissive", "verified_restricted"),
        default="unverified",
    )
    probe.add_argument("--output", type=Path)
    return parser


def main() -> None:
    args = _parser().parse_args()
    if args.command == "trial":
        actual = _sha256(args.checkpoint)
        if actual != args.expected_checkpoint_sha256.lower():
            raise SystemExit("checkpoint SHA-256 mismatch")
        trial = _run_trial(
            runtime_python=args.runtime_python,
            checkpoint=args.checkpoint,
            checkpoint_sha256=actual,
            score=args.score,
            timeout_seconds=args.timeout_seconds,
        )
        print(json.dumps(asdict(trial), sort_keys=True))
        return

    report = run_admission_probe(
        runtime_python=args.runtime_python,
        checkpoint=args.checkpoint,
        expected_checkpoint_sha256=args.expected_checkpoint_sha256,
        score=args.score,
        artifact_terms_status=args.artifact_terms_status,
        timeout_seconds=args.timeout_seconds,
    )
    payload = json.dumps(asdict(report), indent=2, sort_keys=True)
    if args.output:
        args.output.write_text(payload + "\n", encoding="utf-8")
    else:
        print(payload)


if __name__ == "__main__":
    main()
