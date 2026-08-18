"""Regression tests for OSS bakeoff evaluation framework fixes.

Covers bugs found after merging PR #222:
1. Missing Path import in _compute_transcription_metrics
2. Redundant Note.from_dict() on already-Note objects (crash)
3. music21 BytesIO parsing bug producing IndexError
4. None values crashing _compute_category_aggregate
5. Wrong metric key names in transcription aggregate
6. Audio format detection for m4a/mp3 (magic byte detection)
7. Eligibility check moved after inference (not before) to preserve timing measurement
"""

from __future__ import annotations

import json
import os
import tempfile
from contextlib import suppress
from pathlib import Path
from unittest.mock import MagicMock

import pytest


class TestTranscriptionMetricsPathImport:
    """Bug: _compute_transcription_metrics used Path without importing it."""

    def test_compute_transcription_metrics_has_reference_midi(self):
        """Function should work when clip.reference_midi exists (uses Path internally)."""
        from evaluation.engines import _compute_transcription_metrics
        from evaluation.models import EvalClip

        # Create a minimal MIDI file with one note
        midi_bytes = _make_minimal_midi()

        with tempfile.NamedTemporaryFile(suffix=".mid", delete=False) as f:
            f.write(midi_bytes)
            midi_path = f.name

        try:
            clip = EvalClip(
                id="test",
                audio="/dev/null",
                category="solo_piano",
                reference_midi=midi_path,
            )
            output = {"notes": [{"pitch": 60, "start": 0.0, "end": 0.5, "velocity": 64}]}

            metrics = _compute_transcription_metrics(output, clip)
            assert metrics is not None
            assert "note_f1" in metrics
        finally:
            os.unlink(midi_path)

    def test_compute_no_reference_returns_empty(self):
        """Without reference_midi, metrics should be empty dict (no crash)."""
        from evaluation.engines import _compute_transcription_metrics
        from evaluation.models import EvalClip

        clip = EvalClip(id="test", audio="/dev/null", category="solo_piano", reference_midi=None)
        metrics = _compute_transcription_metrics({"notes": []}, clip)
        assert metrics == {}


class TestNoteConversion:
    """Bug: _compute_transcription_metrics called Note.from_dict on Note objects."""

    def test_ref_notes_not_double_wrapped(self):
        """_midi_to_notes returns Note objects; they should NOT be re-wrapped."""
        from evaluation.benchmark import _midi_to_notes
        from evaluation.engines import _compute_transcription_metrics
        from evaluation.models import EvalClip

        midi_bytes = _make_minimal_midi()
        ref_notes = _midi_to_notes(midi_bytes)

        # ref_notes should be Note objects
        from evaluation.transcription_metrics import Note

        assert isinstance(ref_notes[0], Note)

        # _compute_transcription_metrics should accept these without crashing
        with tempfile.NamedTemporaryFile(suffix=".mid", delete=False) as f:
            f.write(midi_bytes)
            midi_path = f.name

        try:
            clip = EvalClip(
                id="test",
                audio="/dev/null",
                category="solo_piano",
                reference_midi=midi_path,
            )
            output = {"notes": [{"pitch": 60, "start": 0.0, "end": 0.5, "velocity": 64}]}
            metrics = _compute_transcription_metrics(output, clip)
            assert metrics is not None
        finally:
            os.unlink(midi_path)


class TestMusic21Parsing:
    """Bug: music21 converter.parse(BytesIO) triggers MuseData format bug."""

    def test_harmony_adapter_parses_midi_bytes(self):
        """Music21HarmonyAdapter.analyze_harmony should work with raw MIDI bytes."""
        pytest.importorskip("music21")

        from evaluation.engines.harmony import Music21HarmonyAdapter

        midi_bytes = _make_minimal_midi()
        adapter = Music21HarmonyAdapter()
        result = adapter.analyze_harmony(midi_bytes)

        assert "key" in result
        assert "chords" in result
        assert "cadences" in result


class TestAggregateMetricsNoneHandling:
    """Bug: None values in metrics dict crash _compute_category_aggregate."""

    def test_none_metrics_do_not_crash_aggregate(self):
        """Aggregate computation should handle None metric values gracefully."""
        from evaluation.engines import (
            EngineEvalResult,
            _compute_category_aggregate,
        )

        # Simulate a result with None metrics (e.g. harmony clip without reference)
        result_with_none = EngineEvalResult(
            engine_name="test",
            clip_id="c1",
            category="harmony",
            success=True,
            metrics={"key_correct": None, "chord_f1": None, "bpm_absolute_error": None},
        )

        report = _compute_category_aggregate([result_with_none], "harmony")
        assert report["macro_key_accuracy"] == 0
        assert report["macro_chord_f1"] == 0

    def test_none_transcription_metrics_do_not_crash(self):
        """Same for transcription category."""
        from evaluation.engines import EngineEvalResult, _compute_category_aggregate

        result = EngineEvalResult(
            engine_name="test",
            clip_id="c1",
            category="transcription",
            success=True,
            metrics={"note_f1": None, "note_precision": None, "note_recall": None},
        )

        report = _compute_category_aggregate([result], "transcription")
        assert "macro_note_f1" in report


class TestMetricKeyNames:
    """Bug: Wrong metric key names in _compute_category_aggregate."""

    def test_harmony_uses_key_correct_not_key_accuracy(self):
        """Harmony aggregate should look for 'key_correct', not 'key_accuracy'."""
        from evaluation.engines import EngineEvalResult, _compute_category_aggregate

        result = EngineEvalResult(
            engine_name="test",
            clip_id="c1",
            category="harmony",
            success=True,
            metrics={"key_correct": True, "chord_f1": 0.8},
        )

        report = _compute_category_aggregate([result], "harmony")
        assert report["macro_key_accuracy"] == 1.0
        assert report["macro_chord_f1"] == 0.8

    def test_transcription_uses_note_precision_not_precision(self):
        """Transcription aggregate should use note_precision, not precision."""
        from evaluation.engines import EngineEvalResult, _compute_category_aggregate

        result = EngineEvalResult(
            engine_name="test",
            clip_id="c1",
            category="transcription",
            success=True,
            metrics={"note_f1": 0.9, "note_precision": 0.8, "note_recall": 0.85},
        )

        report = _compute_category_aggregate([result], "transcription")
        assert report["macro_precision"] == 0.8
        assert report["macro_recall"] == 0.85
        assert report["macro_note_f1"] == 0.9

    def test_beat_tracking_uses_beat_f1_not_f_measure(self):
        """Beat tracking aggregate should look for 'beat_f1', not 'f_measure'."""
        from evaluation.engines import EngineEvalResult, _compute_category_aggregate

        result = EngineEvalResult(
            engine_name="test",
            clip_id="c1",
            category="beat_tracking",
            success=True,
            metrics={"beat_f1": 0.85, "beat_precision": 0.9, "beat_recall": 0.8},
        )

        report = _compute_category_aggregate([result], "beat_tracking")
        assert report["macro_f_measure"] == 0.85


class TestAudioFormatDetection:
    """Bug: piano_transcription and transkun adapters failed on m4a/mp3 files.

    soundfile/libsndfile doesn't support m4a; adapters need format detection
    to use temp files with correct extensions for audioread backend.
    Also: librosa beat_track returns numpy array for tempo, causing float() crash.
    """

    @pytest.fixture(autouse=True)
    def _restore_modules(self):
        """Restore modules that may have been mocked by test_wrappers.py."""
        import sys

        saved = {}
        for mod_name in ["librosa", "soundfile", "basic_pitch", "basic_pitch.inference"]:
            if mod_name in sys.modules and isinstance(sys.modules[mod_name], MagicMock):
                saved[mod_name] = sys.modules[mod_name]
                del sys.modules[mod_name]
        try:
            yield
        finally:
            for mod_name in saved:
                with suppress(KeyError):
                    del sys.modules[mod_name]

    @pytest.mark.integration
    @pytest.mark.skipif(
        not os.path.isfile(f"{os.environ.get('TEST_FIXTURES_DIR', '')}/real-piano.m4a"),
        reason="TEST_FIXTURES_DIR env var not set or m4a fixture missing",
    )
    def test_piano_transcription_handles_m4a(self):
        from evaluation.engines.transcription import PianoTranscriptionAdapter

        if not PianoTranscriptionAdapter().is_available():
            pytest.skip("piano_transcription not installed")

        fixtures_dir = os.environ["TEST_FIXTURES_DIR"]
        m4a_path = f"{fixtures_dir}/real-piano.m4a"

        adapter = PianoTranscriptionAdapter(device="cpu")
        adapter.prepare()

        with open(m4a_path, "rb") as f:
            audio_bytes = f.read()

        result = adapter.transcribe(audio_bytes)
        assert result["num_notes"] > 0
        assert len(result["notes"]) == result["num_notes"]

    def test_piano_transcription_model_sample_rate(self):
        """The model is trained at 16 kHz; adapter must feed 16 kHz audio.

        Regression for the zero-match bug: the adapter previously resampled
        audio to 44.1 kHz, but the model's spectrogram hop is 160 samples/frame
        and the post-processor assumes 100 frames/s. 44.1 kHz input stretches
        every onset/offset by 44100/16000 = 2.756x, producing 0 note matches.
        """
        from evaluation.engines.transcription import PianoTranscriptionAdapter

        assert PianoTranscriptionAdapter.MODEL_SAMPLE_RATE == 16000

    @pytest.mark.integration
    @pytest.mark.skipif(
        not os.path.isfile(f"{os.environ.get('TEST_FIXTURES_DIR', '')}/real-piano.m4a"),
        reason="TEST_FIXTURES_DIR env var not set or m4a fixture missing",
    )
    def test_piano_transcription_output_time_aligned(self):
        """Predicted note span must match audio duration, not be stretched 2.76x."""
        import librosa

        from evaluation.engines.transcription import PianoTranscriptionAdapter

        if not PianoTranscriptionAdapter().is_available():
            pytest.skip("piano_transcription not installed")

        fixtures_dir = os.environ["TEST_FIXTURES_DIR"]
        m4a_path = f"{fixtures_dir}/real-piano.m4a"

        # True audio duration
        audio, sr = librosa.load(m4a_path, sr=None, mono=True)
        audio_duration = len(audio) / sr

        adapter = PianoTranscriptionAdapter(device="cpu")
        adapter.prepare()

        with open(m4a_path, "rb") as f:
            audio_bytes = f.read()

        result = adapter.transcribe(audio_bytes)
        assert result["num_notes"] > 0

        pred_duration = max(n["end"] for n in result["notes"])
        ratio = pred_duration / audio_duration
        # Tolerate small model output edge effects; the sample-rate bug
        # produced ~2.76x. If alignment regresses, this fails loudly.
        assert abs(ratio - 1.0) < 0.3, (
            f"predicted span {pred_duration:.2f}s vs audio {audio_duration:.2f}s "
            f"(ratio {ratio:.2f}) - sample-rate mismatch regression"
        )

    @pytest.mark.integration
    @pytest.mark.skipif(
        not os.path.isfile(f"{os.environ.get('TEST_FIXTURES_DIR', '')}/real-piano.m4a"),
        reason="TEST_FIXTURES_DIR env var not set or m4a fixture missing",
    )
    def test_basic_pitch_handles_m4a(self):
        """BasicPitchAdapter should successfully transcribe m4a files."""
        from evaluation.engines.transcription import BasicPitchAdapter

        if not BasicPitchAdapter().is_available():
            pytest.skip("basic_pitch not installed")

        fixtures_dir = os.environ["TEST_FIXTURES_DIR"]
        m4a_path = f"{fixtures_dir}/real-piano.m4a"

        adapter = BasicPitchAdapter()

        with open(m4a_path, "rb") as f:
            audio_bytes = f.read()

        result = adapter.transcribe(audio_bytes)
        assert result["num_notes"] > 0

    def test_librosa_tempo_is_scalar(self):
        """librosa.beat_track returns numpy array for tempo; adapter should convert to float."""
        import numpy as np

        from evaluation.engines.beat_tracking import LibrosaBeatAdapter

        if not LibrosaBeatAdapter().is_available():
            pytest.skip("librosa not installed")

        adapter = LibrosaBeatAdapter()
        adapter.prepare()

        # Use a simple sine wave as audio
        sr = 44100
        duration = 5.0
        t = np.linspace(0, duration, int(sr * duration))
        audio = (np.sin(2 * np.pi * 1.0 * t) * 0.3).astype(np.float32)

        # Write to temp WAV
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            import soundfile as sf

            sf.write(f.name, audio, sr)
            tmp_path = f.name

        try:
            with open(tmp_path, "rb") as f:
                audio_bytes = f.read()
            output = adapter.estimate_beats(audio_bytes)
            assert isinstance(output["bpm"], float)
            assert output["bpm"] > 0
        finally:
            os.unlink(tmp_path)


class TestEligibilityAfterInference:
    """Bug: eligibility check caused early return before inference, breaking timing measurement.

    The check should only skip metric computation, not the actual inference run.
    """

    @pytest.fixture(autouse=True)
    def _restore_modules(self):
        """Restore modules that may have been mocked by test_wrappers.py."""
        import sys

        saved = {}
        for mod_name in ["librosa", "soundfile", "basic_pitch", "basic_pitch.inference"]:
            if mod_name in sys.modules and isinstance(sys.modules[mod_name], MagicMock):
                saved[mod_name] = sys.modules[mod_name]
                del sys.modules[mod_name]
        try:
            yield
        finally:
            for mod_name in saved:
                with suppress(KeyError):
                    del sys.modules[mod_name]

    @pytest.mark.integration
    def test_ineligible_clip_still_runs_inference(self):
        """Ineligible clips (no ref MIDI) should still run inference for diagnostics."""
        from evaluation.engines import _run_clip_on_engine
        from evaluation.engines.transcription import BasicPitchAdapter
        from evaluation.models import EvalClip

        if not BasicPitchAdapter().is_available():
            pytest.skip("basic_pitch not installed")

        piano_simple = (
            Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "piano-simple.m4a"
        )
        # Create a clip with audio but no reference_midi
        clip = (
            EvalClip(
                id="test_no_ref",
                audio=str(piano_simple),
                category="solo_piano",
                reference_midi=None,
            )
            if piano_simple.is_file()
            else None
        )

        if clip is None:
            pytest.skip("test fixture not found")

        adapter = BasicPitchAdapter()
        result = _run_clip_on_engine(adapter, clip, "transcription", warmup=False)

        # Inference should have run (not short-circuited by eligibility check)
        assert result.success is True
        # But metrics should be empty (not scored)
        assert result.metrics == {}
        # And diagnostics should indicate ineligibility
        assert result.diagnostics.get("eligibility") == "ineligible"
        # Runtime should be measured (not 0.0 like the old early-return bug)
        assert result.runtime_s > 0

    def test_eligibility_reason_set_for_missing_reference(self):
        """_check_clip_eligibility should return a reason for missing reference MIDI."""
        from evaluation.engines import _check_clip_eligibility
        from evaluation.models import EvalClip

        clip = EvalClip(id="test", audio="/dev/null", category="solo_piano", reference_midi=None)
        reason = _check_clip_eligibility("transcription", clip)
        assert reason is not None
        assert "reference MIDI" in reason

    def test_eligible_clip_no_eligibility_reason(self):
        """_check_clip_eligibility should return None when reference MIDI exists."""
        from evaluation.engines import _check_clip_eligibility
        from evaluation.models import EvalClip

        midi_path = _make_minimal_midi()
        with tempfile.NamedTemporaryFile(suffix=".mid", delete=False) as f:
            f.write(midi_path)
            midi_file = f.name

        try:
            clip = EvalClip(
                id="test", audio="/dev/null", category="solo_piano", reference_midi=midi_file
            )
            reason = _check_clip_eligibility("transcription", clip)
            assert reason is None
        finally:
            os.unlink(midi_file)


# --- Helpers ---


def _make_minimal_midi() -> bytes:
    """Create a minimal MIDI file with a single C4 note for testing."""
    import struct

    def _var_len(value: int) -> bytes:
        buf = bytearray()
        buf.append(value & 0x7F)
        value >>= 7
        while value:
            buf.append(0x80 | (value & 0x7F))
            value >>= 7
        buf.reverse()
        return bytes(buf)

    ppq = 480
    tempo_bpm = 120
    ticks_per_beat = int(60_000_000 / tempo_bpm)

    track_data = bytearray()
    # Tempo
    track_data.extend(_var_len(0))
    track_data.extend(bytes([0xFF, 0x51, 0x03]))
    track_data.extend(
        bytes([(ticks_per_beat >> 16) & 0xFF, (ticks_per_beat >> 8) & 0xFF, ticks_per_beat & 0xFF])
    )
    # Note on
    track_data.extend(_var_len(0))
    track_data.extend(bytes([0x90, 60, 64]))
    # Note off (1 beat later)
    track_data.extend(_var_len(ppq))
    track_data.extend(bytes([0x80, 60, 0]))
    # End of track
    track_data.extend(_var_len(0))
    track_data.extend(bytes([0xFF, 0x2F, 0x00]))

    header = struct.pack(">HHH", 0, 1, ppq)
    track_chunk = b"MTrk" + struct.pack(">I", len(track_data)) + bytes(track_data)
    return b"MThd" + struct.pack(">I", 6) + header + track_chunk


class TestBytesJSONRoundTrip:
    """Regression: MIDI bytes in result JSON must not rely on eval().

    Per-clip results are serialized with _BytesJSONEncoder, which encodes bytes
    as {"__base64__": ...}; the artifact decoder must decode that explicitly.
    """

    def test_encoder_round_trips_midi_bytes_losslessly(self):
        from evaluation.engines import _BytesJSONEncoder

        midi = _make_minimal_midi()
        # Embed bytes with a NULL byte and non-ASCII to exercise escaping.
        payload = midi + b"\x00\xff\x10\x00garbage"
        encoded = json.dumps({"output": {"midi": payload}}, cls=_BytesJSONEncoder)
        decoded = json.loads(encoded)
        assert decoded["output"]["midi"]["__base64__"].startswith("TVRoZAAA")
        assert decoded["output"]["midi"]["__base64__"] == (
            __import__("base64").b64encode(payload).decode("ascii")
        )

    def test_artifact_decoder_recovers_base64_without_eval(self):
        import base64 as b64

        from evaluation.analysis.qualitative_artifacts import _midi_bytes_from_result

        midi = _make_minimal_midi()
        result = {"output": {"midi": {"__base64__": b64.b64encode(midi).decode("ascii")}}}
        assert _midi_bytes_from_result(result) == midi

    def test_artifact_decoder_rejects_bytes_repr_string(self):
        """A legacy str(bytes) repr must NOT be accepted (no eval fallback)."""
        from evaluation.analysis.qualitative_artifacts import _midi_bytes_from_result

        result = {"output": {"midi": repr(_make_minimal_midi())}}
        assert _midi_bytes_from_result(result) == b""
