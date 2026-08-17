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
        assert grid.heuristic_confidence >= 0.5
        assert len(grid.measure_boundaries) == 2

    def test_no_downbeats_no_meter_invention(self):
        """Without downbeats, meter must be None — never invent 4/4."""
        beats = [0.0, 0.5, 1.0, 1.5]
        grid = build_metrical_grid(beats)
        assert grid.inferred_meter is None
        assert grid.heuristic_confidence == 0.0

    def test_too_few_beats(self):
        grid = build_metrical_grid([0.0])
        assert grid.inferred_meter is None

    def test_no_beats(self):
        grid = build_metrical_grid([])
        assert grid.measure_boundaries == []

    def test_triplet_beats(self):
        beats = list(np.arange(0, 4, 1 / 3))
        downbeats = [0.0, 1.0, 2.0, 3.0]
        grid = build_metrical_grid(beats, downbeats)
        assert grid.inferred_meter is not None

    def test_downbeats_with_different_count(self):
        """When beat count between downbeats varies, meter should still be inferred."""
        beats = list(np.arange(0, 4, 0.25))
        downbeats = [0.0, 1.0, 2.0, 3.0]
        grid = build_metrical_grid(beats, downbeats)
        assert grid.inferred_meter == (4, 4)

    def test_beats_but_no_downbeats(self):
        """Beats exist but meter confidence is zero."""
        beats = [0.0, 0.5, 1.0, 1.5, 2.0]
        grid = build_metrical_grid(beats)
        assert grid.global_beats()
        assert grid.inferred_meter is None

    def test_jittered_downbeats_snap_to_beat_grid(self):
        """Jittered downbeat timestamps must not create irregular measure
        boundaries: a 4.02 s boundary on a 0.5 s beat grid forces sub-tactus
        quantization steps that music21 cannot engrave to MusicXML."""
        beats = [i * 0.5 for i in range(9)]
        downbeats = [0.0, 2.0, 4.02]
        grid = build_metrical_grid(beats, downbeats)
        assert grid.inferred_meter == (4, 4)
        assert grid.measure_boundaries == [0.0, 2.0, 4.0], grid.measure_boundaries

    def test_irreconcilable_downbeats_still_anchor(self):
        """Downbeats far off the beat grid still yield a bounded grid (snapped
        to the nearest beat) rather than crashing or inventing a meter."""
        beats = [i * 0.5 for i in range(9)]
        downbeats = [0.0, 2.03, 4.0]
        grid = build_metrical_grid(beats, downbeats)
        assert len(grid.measure_boundaries) >= 2
        assert all(round(b * 2) == b * 2 for b in grid.measure_boundaries)

    def test_irregular_downbeats_do_not_claim_meter(self):
        """Genuinely irregular downbeats (not on a stable tactus) must not
        claim a meter. Claiming one would force the adaptive quantizer into
        sub-tactus step sizes that music21 cannot engrave, crashing the score
        pipeline on real recordings."""
        beats = [0.0, 0.8, 1.6, 2.4, 3.2, 4.0, 4.8, 5.6, 6.4]
        downbeats = [0.0, 0.8, 2.4, 4.8, 5.6]
        grid = build_metrical_grid(beats, downbeats)
        assert grid.inferred_meter is None
        assert grid.measure_boundaries == []
        assert grid.heuristic_confidence == 0.0
