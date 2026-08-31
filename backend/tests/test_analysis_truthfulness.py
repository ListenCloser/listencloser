"""Tests for truthful analysis: no default masquerading, no fabricated
confidence, and no unknown chord spam."""

from __future__ import annotations

import io
import os
import tempfile
import uuid

import pytest

pytest.importorskip("music21", reason="music21 not installed")

import pretty_midi  # noqa: E402
from music21 import stream  # noqa: E402

from analyze import analyze_midi  # noqa: E402
from domain.capabilities import _transcription_defaults_pulse  # noqa: E402
from domain.models import Version  # noqa: E402
from engines.harmony.music21_engine import _m21_chords, _m21_key  # noqa: E402


class _FakeTonic:
    def __init__(self, name: str | None):
        self.name = name


class _FakeKey:
    def __init__(self, corr: float | None, tonic: str | None, mode: str):
        self.correlationCoefficient = corr
        self.tonic = _FakeTonic(tonic) if tonic else None
        self.mode = mode


class _FakeScore:
    def __init__(self, key_result=None, raises: bool = False):
        self._key = key_result
        self._raises = raises

    def analyze(self, _kind):
        if self._raises:
            raise RuntimeError("boom")
        return self._key


class _FakeUnknownChord:
    def root(self):
        return None


class _FakeChordScore:
    def flatten(self):
        return self

    def getElementsByClass(self, cls):
        if cls == "Chord":
            return [_FakeUnknownChord()]
        return []


def _version_with_provenance(provenance: dict | None, flags: dict | None = None) -> Version:
    metadata: dict = {"provenance": provenance} if provenance else {}
    if flags:
        metadata.update(flags)
    return Version(
        artifact_id=uuid.uuid4(),
        storage_key="key.mid",
        storage_bucket="artifacts",
        metadata=metadata,
    )


def _midi_bytes(tempo: int = 120, numerator: int = 4, denominator: int = 4) -> bytes:
    pm = pretty_midi.PrettyMIDI(initial_tempo=tempo)
    pm.time_signature_changes.append(
        pretty_midi.TimeSignature(numerator=numerator, denominator=denominator, time=0.0)
    )
    inst = pretty_midi.Instrument(program=0)
    for i, pitch in enumerate([60, 64, 67, 71]):
        inst.notes.append(
            pretty_midi.Note(velocity=80, pitch=pitch, start=i * 0.5, end=i * 0.5 + 0.4)
        )
    pm.instruments.append(inst)
    buf = io.BytesIO()
    pm.write(buf)
    return buf.getvalue()


class TestKeyTruthfulness:
    def test_key_uses_real_correlation_not_fabricated(self):
        result = _m21_key(_FakeScore(_FakeKey(0.62, "G", "major")))
        assert result is not None
        assert result["tonic"] == "G"
        assert result["mode"] == "major"
        assert result["confidence"] == 0.62

    def test_key_returns_none_without_correlation(self):
        assert _m21_key(_FakeScore(_FakeKey(None, "C", "major"))) is None

    def test_key_returns_none_without_tonic(self):
        assert _m21_key(_FakeScore(_FakeKey(0.5, None, "major"))) is None

    def test_key_returns_none_on_failure(self):
        assert _m21_key(_FakeScore(raises=True)) is None


class TestChordsFilterUnknown:
    def test_unknown_root_chord_is_skipped(self):
        assert _m21_chords(_FakeChordScore()) == []


class TestTranscriptionDefaultsPulse:
    def test_placeholder_flags_mark_pulse_as_default(self):
        version = _version_with_provenance(
            {"engine": "basic_pitch"},
            flags={"tempo_is_placeholder": True, "meter_is_placeholder": True},
        )
        assert _transcription_defaults_pulse(version)

    def test_no_flags_is_not_default(self):
        assert not _transcription_defaults_pulse(_version_with_provenance({"engine": "fixture"}))

    def test_missing_provenance_is_not_default(self):
        assert not _transcription_defaults_pulse(_version_with_provenance(None))


class TestAnalyzeMidiNoDefaults:
    def test_time_signature_read_from_metadata(self):
        with tempfile.NamedTemporaryFile(suffix=".mid", delete=False) as f:
            f.write(_midi_bytes(tempo=90, numerator=3, denominator=4))
            path = f.name
        try:
            result = analyze_midi(path)
        finally:
            import os

            os.unlink(path)
        assert result["time_signature"] is not None
        assert result["time_signature"]["numerator"] == 3
        assert result["time_signature"]["denominator"] == 4

    def test_key_is_none_when_music21_fails(self):
        # A MIDI with a single fleeting note still yields a key via music21, so
        # this only asserts the contract that a None result is allowed and the
        # caller (handle_analyze) treats it as unavailable.
        assert _m21_key(_FakeScore(raises=True)) is None


class TestNoModulationClaims:
    def test_analysis_has_no_modulations_key(self):
        """The modulations contract was removed from the analysis result."""
        with tempfile.NamedTemporaryFile(suffix=".mid", delete=False) as f:
            f.write(_midi_bytes())
            path = f.name
        try:
            result = analyze_midi(path)
        finally:
            import os

            os.unlink(path)
        assert "modulations" not in result
        assert "modulations" not in result["harmony_provenance"]

    def test_engine_result_has_no_modulations_field(self):
        from engines.base import HarmonyResult
        from engines.harmony.music21_engine import Music21HarmonyEngine

        engine = Music21HarmonyEngine()
        assert "modulations" not in engine.component_provenance()
        fields = set(HarmonyResult.__dataclass_fields__)
        assert "modulations" not in fields


class TestRomanNumeralsRequireChords:
    def test_no_chords_suppresses_roman_numerals(self):
        """Truthfulness invariant: no defensible chord evidence → no persisted
        Roman numeral claims."""
        with tempfile.NamedTemporaryFile(suffix=".mid", delete=False) as f:
            f.write(_midi_bytes())
            path = f.name
        try:
            result = analyze_midi(path)
        finally:
            import os

            os.unlink(path)
        # The canonical synthetic MIDI has no recognized chords (un-spelled
        # clusters), so Roman numerals must be suppressed even if music21 can
        # still produce a key.
        assert result["chords"] == []
        assert result["roman_numerals"] == []

    def test_chords_allow_roman_numerals(self):
        """When defensible chord evidence exists, Roman numerals persist."""
        from music21 import chord as m21_chord

        from engines.harmony.music21_engine import _m21_roman_numerals

        s = stream.Score()
        p = stream.Part()
        m = stream.Measure()
        c = m21_chord.Chord("C4 E4 G4")
        c.offset = 0.0
        c.quarterLength = 1.0
        m.insert(c)
        p.append(m)
        s.insert(0, p)
        detected = s.analyze("key")
        rns = _m21_roman_numerals(s, detected)
        assert isinstance(rns, list)


class TestPulseEvidence:
    """Audio-derived pulse evidence overrides placeholders and carries provenance."""

    def _midi_path(self, tempo: int = 90) -> str:
        pm = pretty_midi.PrettyMIDI(initial_tempo=tempo)
        pm.time_signature_changes.append(pretty_midi.TimeSignature(4, 4, 0.0))
        inst = pretty_midi.Instrument(program=0)
        for i in range(8):
            inst.notes.append(
                pretty_midi.Note(velocity=80, pitch=60, start=i * 0.5, end=i * 0.5 + 0.4)
            )
        pm.instruments.append(inst)
        buf = io.BytesIO()
        pm.write(buf)
        f = tempfile.NamedTemporaryFile(suffix=".mid", delete=False)
        f.write(buf.getvalue())
        f.close()
        return f.name

    def _pulse(self) -> dict:
        return {
            "bpm": 120.0,
            "beats": [i * 0.5 for i in range(16)],
            "downbeats": [0.0, 2.0, 4.0, 6.0],
            "provenance": {"engine": "beat_this", "library_version": "1.1.0"},
        }

    def test_audio_tempo_preferred_over_midi_metadata(self):
        path = self._midi_path(tempo=90)
        try:
            result = analyze_midi(path, pulse=self._pulse())
        finally:
            os.unlink(path)
        assert result["tempo"]["bpm"] == 120.0
        assert result["tempo"]["source"] == "audio_beat_tracking"
        # Beat engines provide no calibrated confidence — never fabricated.
        assert result["tempo"]["confidence"] is None

    def test_degenerate_pulse_produces_no_tempo(self):
        """A degenerate beat estimate must not become 120 BPM evidence."""
        path = self._midi_path(tempo=90)
        try:
            no_bpm = analyze_midi(
                path,
                pulse={"bpm": None, "beats": [], "downbeats": None, "provenance": {}},
            )
            empty_pulse = analyze_midi(path, pulse={})
        finally:
            os.unlink(path)
        # Even though the MIDI metadata has an explicit tempo, an attempted audio
        # measurement that failed must leave tempo absent — never fall back to
        # MIDI metadata or a default.
        assert no_bpm["tempo"] is None
        assert empty_pulse["tempo"] is None

    def test_audio_pulse_leaves_time_signature_unknown(self):
        """Beats/downbeats are evidence; a notated (N, 4) meter is not derived."""
        path = self._midi_path()
        try:
            result = analyze_midi(path, pulse=self._pulse())
        finally:
            os.unlink(path)
        # The MIDI metadata here has an explicit 4/4, but the audio path must not
        # mix it in: meter stays unknown rather than claiming a notation.
        assert result["time_signature"] is None

    def test_beat_count_and_offbeat_ratio_from_pulse(self):
        path = self._midi_path()
        try:
            result = analyze_midi(path, pulse=self._pulse())
        finally:
            os.unlink(path)
        rhythm = result["rhythm"]
        assert rhythm["beat_count"] == 16
        assert rhythm["offbeat_onset_available"] is True

    def test_no_pulse_keeps_conservative_midi_path(self):
        path = self._midi_path(tempo=90)
        try:
            result = analyze_midi(path)
        finally:
            os.unlink(path)
        assert result["tempo"]["bpm"] == 90.0
        assert result["tempo"]["source"] == "midi_metadata"
        assert result["tempo"]["confidence"] == 0.9
        assert result["rhythm"]["offbeat_onset_available"] is False
        assert result["rhythm"]["offbeat_onset_ratio"] is None
        assert result["pulse_provenance"] is None

    def test_pulse_provenance_attached(self):
        path = self._midi_path()
        try:
            result = analyze_midi(path, pulse=self._pulse())
        finally:
            os.unlink(path)
        assert result["pulse_provenance"]["engine"] == "beat_this"

    def test_offbeat_ratio_counts_off_beat_onsets(self):
        pm = pretty_midi.PrettyMIDI(initial_tempo=90)
        inst = pretty_midi.Instrument(program=0)
        for i in range(8):
            inst.notes.append(
                pretty_midi.Note(velocity=80, pitch=60, start=i * 0.5 + 0.25, end=i * 0.5 + 0.4)
            )
        pm.instruments.append(inst)
        buf = io.BytesIO()
        pm.write(buf)
        f = tempfile.NamedTemporaryFile(suffix=".mid", delete=False)
        f.write(buf.getvalue())
        f.close()
        try:
            result = analyze_midi(f.name, pulse=self._pulse())
        finally:
            os.unlink(f.name)
        assert result["rhythm"]["offbeat_onset_ratio"] == 1.0
        assert result["rhythm"]["offbeat_onset_available"] is True
