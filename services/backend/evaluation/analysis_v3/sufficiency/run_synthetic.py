"""Run deterministic synthetic evidence-sufficiency perturbation probes."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .perturbations import (
    event_localization_summary,
    metric_grid_shift_sensitivity,
    span_boundary_sensitivity,
)


def run_synthetic_sensitivity() -> dict[str, Any]:
    """Return raw sensitivity measurements without musical claim thresholds."""
    metric_grid = metric_grid_shift_sensitivity(
        [0.98, 1.98, 2.98],
        [1.0, 2.0, 3.0],
        [0.01, 0.02, 0.05, 0.1],
    )
    localization_coverage = {
        "complete": event_localization_summary(3, 3, [0.01, 0.01, 0.01]),
        "sparse_same_matched_error": event_localization_summary(3, 1, [0.01]),
    }
    span_boundaries = span_boundary_sensitivity(
        [0.0, 1.0, 2.0, 3.0, 4.0],
        [0.0, 0.0, 10.0, 10.0, 10.0],
        0.0,
        3.0,
        [(0.0, 1.0), (1.0, 0.0), (0.0, -1.0)],
    )
    return {
        "evidence_class": "DETERMINISTIC_ERROR_PROPAGATION",
        "scope": "evaluation_only",
        "semantic_thresholds": "none; downstream claims own tolerances",
        "metric_grid_shift": metric_grid,
        "event_localization_coverage": localization_coverage,
        "span_boundary_shift": span_boundaries,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()

    payload = json.dumps(run_synthetic_sensitivity(), indent=2, sort_keys=True) + "\n"
    if args.output is None:
        print(payload, end="")
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
