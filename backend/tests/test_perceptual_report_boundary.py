from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from domain.perceptual_report import (
    PerceptualEvidenceReport as LightweightPerceptualEvidenceReport,
)
from perceptual_evidence import PerceptualEvidenceReport as WorkerPerceptualEvidenceReport

BACKEND_ROOT = Path(__file__).resolve().parents[1]


def test_worker_module_reexports_canonical_report_contract() -> None:
    assert WorkerPerceptualEvidenceReport is LightweightPerceptualEvidenceReport


def test_api_entrypoint_import_does_not_require_dsp_runtime() -> None:
    code = r'''
import importlib.abc
import sys

blocked_roots = {"librosa", "numpy", "soundfile", "perceptual_evidence"}


class BlockDSP(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split(".", 1)[0] in blocked_roots:
            raise ImportError(f"blocked worker/DSP import: {fullname}")
        return None


sys.meta_path.insert(0, BlockDSP())
import main  # noqa: F401

assert not blocked_roots.intersection(sys.modules)
'''
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=BACKEND_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
