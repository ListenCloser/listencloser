"""Reproducible release-preservation evidence for adaptive quantization.

Runs the real-audio notation pipeline (transcribe -> beat track -> adaptive
quantize) on the canonical solo-piano fixture (real-piano.m4a) and reports how
cross-measure note releases are preserved: a note that sustains past the barline
of the measure it starts in keeps its full extent instead of being clamped to
the onset measure's boundary.

The "legacy" comparison simulates the pre-fix behavior (release snapped to the
onset measure's end) so the before/after contrast is reproducible without the
old source.

Usage:
    PYTHONPATH=. python scripts/notation_release_preservation_evidence.py \
        [fixture.m4a] [--out reports/notation_release_preservation.png]

Exit code is nonzero if any cross-bar release is clamped to its onset measure's
boundary (i.e. the fix regresses).
"""

from __future__ import annotations

import argparse
import io
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pretty_midi  # noqa: E402

from music_features import (  # noqa: E402
    decode_audio_to_wav,
    estimate_beats_with_engine,
    transcribe_with_engine,
)
from notation.grid import build_metrical_grid, measure_boundary_end  # noqa: E402
from notation.quantize import _measure_index, adaptive_quantize  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_FIXTURE = REPO_ROOT / "tests" / "fixtures" / "real-piano.m4a"


def _notes(midi_bytes: bytes) -> list[tuple[int, float, float]]:
    pm = pretty_midi.PrettyMIDI(io.BytesIO(midi_bytes))
    return [
        (n.pitch, float(n.start), float(n.end))
        for inst in pm.instruments
        if not inst.is_drum
        for n in inst.notes
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("fixture", nargs="?", default=str(DEFAULT_FIXTURE))
    parser.add_argument(
        "--out",
        default=str(REPO_ROOT / "backend/evaluation/reports/notation_release_preservation.png"),
    )
    args = parser.parse_args()

    audio = Path(args.fixture).read_bytes()
    tr = transcribe_with_engine(audio, profile="general")
    wav = decode_audio_to_wav(audio, fmt="m4a")
    beats = estimate_beats_with_engine(wav, engine_name="beat_this")
    grid = build_metrical_grid(beats["beats"], beats.get("downbeats"))
    if grid.inferred_meter is None or not grid.measure_boundaries:
        raise SystemExit("beat tracking did not produce a metrical grid; cannot run the evidence")

    quantized, report = adaptive_quantize(tr["midi"], grid)
    orig = _notes(tr["midi"])
    out = _notes(quantized)

    cross: list[int] = []
    for i, (_p, s, e) in enumerate(orig):
        sm = _measure_index(s, grid)
        em = _measure_index(e, grid)
        if sm is not None and em is not None and em > sm:
            cross.append(i)

    containing_steps = {s["measure_index"]: s["step_seconds"] for s in report["grid_selections"]}

    legacy_move: list[float] = []
    actual_move: list[float] = []
    clamped = 0
    for i in cross:
        s = orig[i][1]
        m_idx = _measure_index(s, grid)
        onset_end = measure_boundary_end(m_idx, grid.measure_boundaries, grid.beats)
        legacy_move.append(abs(onset_end - orig[i][2]))
        moved = abs(out[i][2] - orig[i][2])
        actual_move.append(moved)
        # A release is only a regression if it was forced onto the onset
        # measure's end while the containing measure's grid had a nearer point
        # (i.e. the release really sustained past the boundary). Releasing
        # exactly at the barline, or quantizing to the boundary as the nearest
        # containing-measure grid point, is legitimate.
        end_midx = _measure_index(orig[i][2], grid)
        step = containing_steps.get(end_midx)
        if (
            step is not None
            and abs(out[i][2] - onset_end) < 1e-6
            and orig[i][2] > onset_end + step * 0.5
        ):
            clamped += 1

    stats = {
        "fixture": args.fixture,
        "note_count": len(orig),
        "cross_bar_notes": len(cross),
        "measure_count": len(grid.measure_boundaries),
        "meter": grid.inferred_meter,
        "legacy_release_mean_movement": round(float(np.mean(legacy_move)), 4),
        "legacy_release_max_movement": round(float(np.max(legacy_move)), 4),
        "actual_release_mean_movement": round(float(np.mean(actual_move)), 4),
        "actual_release_max_movement": round(float(np.max(actual_move)), 4),
        "release_clamped_to_onset_boundary": clamped,
        "grid_selections": report["grid_selections"],
    }
    print(json.dumps(stats, indent=2))

    fig, axes = plt.subplots(1, 2, figsize=(13, 4.6))
    x = np.arange(len(cross))
    axes[0].bar(
        x,
        legacy_move,
        width=0.4,
        label="before (clamped at barline)",
        color="#c0392b",
        alpha=0.85,
    )
    axes[0].bar(
        x + 0.4,
        actual_move,
        width=0.4,
        label="after (preserved)",
        color="#1a7f37",
        alpha=0.85,
    )
    axes[0].set_xlabel("cross-bar note index")
    axes[0].set_ylabel("|release shift| (s)")
    axes[0].set_title(
        f"{Path(args.fixture).name}: release movement on {len(cross)} cross-bar notes"
    )
    axes[0].legend()
    axes[0].axhline(0, color="black", lw=0.8)
    bins = np.linspace(0, max(np.max(legacy_move), np.max(actual_move)), 25)
    axes[1].hist(
        legacy_move,
        bins=bins,
        alpha=0.6,
        label=f"before (mean {np.mean(legacy_move):.2f}s)",
        color="#c0392b",
    )
    axes[1].hist(
        actual_move,
        bins=bins,
        alpha=0.6,
        label=f"after (mean {np.mean(actual_move):.2f}s)",
        color="#1a7f37",
    )
    axes[1].set_xlabel("release movement (s)")
    axes[1].set_ylabel("notes")
    axes[1].set_title("distribution of release movement")
    axes[1].legend()
    fig.tight_layout()
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(str(out_path), dpi=120)
    plt.close(fig)
    print(f"\nwrote {out_path}")

    return 1 if clamped else 0


if __name__ == "__main__":
    raise SystemExit(main())
