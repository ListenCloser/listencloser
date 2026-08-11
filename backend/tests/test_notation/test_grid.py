"""Tests for metrical grid construction."""

from __future__ import annotations

import numpy as np

from notation.grid import build_metrical_grid


class TestMetricalGrid:
    def test_basic_4_4_grid(self):
        beats = [0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5]
        downbeats = [0.0, 2.0]
        grid = build_metrical_grid(beats, downbeats)
        assert grid.inferred_meter == (4, 4)
        assert grid.confidence >= 0.5
        assert len(grid.measure_boundaries) == 2
        assert grid.measure_boundaries == [0.0, 2.0]

    def test_no_downbeats_falls_back(self):
        beats = [0.0, 0.5, 1.0, 1.5]
        grid = build_metrical_grid(beats)
        assert grid.inferred_meter is not None
        assert grid.confidence == 0.3

    def test_too_few_beats(self):
        grid = build_metrical_grid([0.0])
        assert grid.inferred_meter is None
        assert grid.confidence == 0.0

    def test_no_beats(self):
        grid = build_metrical_grid([])
        assert grid.measure_boundaries == []

    def test_triplet_beats(self):
        beats = list(np.arange(0, 4, 1 / 3))
        downbeats = [0.0, 1.0, 2.0, 3.0]
        grid = build_metrical_grid(beats, downbeats)
        assert grid.inferred_meter is not None

    def test_subdivisions_returns_measure_grids(self):
        beats = [0.0, 0.5, 1.0, 1.5]
        grid = build_metrical_grid(beats)
        subs = grid.subdivisions((4, 4))
        assert len(subs) > 0
        assert all(len(s) > 0 for s in subs)
