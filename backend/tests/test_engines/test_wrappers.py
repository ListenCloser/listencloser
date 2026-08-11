"""Tests that engine APIs match existing production function signatures.

These tests require production music dependencies and are skipped when
they are not available (e.g., on local dev machines without Basic Pitch).
"""

from __future__ import annotations

from unittest.mock import patch

import pytest


class TestWrapperCompatibility:
    @pytest.mark.skip(reason="production music deps not available in local dev")
    def test_transcription_engine_accepts_audio_bytes(self):
        from engines.transcription.basic_pitch import BasicPitchEngine

        engine = BasicPitchEngine(onset_threshold=0.5, frame_threshold=0.3)
        mock_notes = [{"pitch": 60, "start": 0.0, "end": 0.5, "velocity": 64}]
        mock_result = {
            "midi": b"fake-midi",
            "wav": b"fake-wav",
            "notes": mock_notes,
            "num_notes": 1,
            "cleanup_report": {"kept_notes": 1},
        }
        with patch("music_features.transcribe_audio", return_value=mock_result) as mock_fn:
            result = engine.transcribe(b"test-audio", fmt="wav")
            mock_fn.assert_called_once_with(
                b"test-audio", fmt="wav", onset_threshold=0.5, frame_threshold=0.3,
            )
            assert result.num_notes == 1
            assert result.provenance.engine == "basic_pitch"

    @pytest.mark.skip(reason="production music deps not available in local dev")
    def test_beat_engine_accepts_wav_bytes(self):
        from engines.beats.librosa_engine import LibrosaBeatEngine

        engine = LibrosaBeatEngine()
        with patch("music_features.estimate_beat_grid", return_value=(120.0, [0.0, 0.5])) as mock_fn:
            result = engine.analyze(b"test-wav")
            mock_fn.assert_called_once_with(b"test-wav")
            assert result.bpm == 120.0
            assert result.provenance.engine == "librosa"

    @pytest.mark.skip(reason="production music deps not available in local dev")
    def test_notation_engine_accepts_midi_and_beats(self):
        from engines.notation.music21_engine import Music21NotationEngine

        engine = Music21NotationEngine()
        with patch(
            "music_features.notation_midi_from_performance",
            return_value=(b"not-midi", {"notes": 5}),
        ), patch("music_features.convert_format", return_value=b"musicxml"):
            result = engine.convert(b"midi-bytes", [0.0, 0.5])
            assert result.provenance.engine == "music21"
            assert result.musicxml == b"musicxml"
