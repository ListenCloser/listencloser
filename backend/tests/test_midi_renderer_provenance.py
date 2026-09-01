from __future__ import annotations

import inspect

import music_features
from domain import capabilities


def test_midi_renderer_metadata_uses_live_renderer_contract(monkeypatch) -> None:
    def renderer(_midi: bytes, sr: int = 32000) -> bytes:
        return b"wav"

    monkeypatch.setattr(music_features, "midi_to_wav", renderer)
    monkeypatch.setattr(music_features, "SOUNDFONT_PATH", "/opt/sounds/custom-piano.sf2")

    assert capabilities._midi_renderer_metadata() == {
        "engine": "fluidsynth",
        "soundfont": "custom-piano.sf2",
        "soundfont_path": "/opt/sounds/custom-piano.sf2",
        "sample_rate_hz": 32000,
    }
    assert capabilities._midi_renderer_metadata(44100)["sample_rate_hz"] == 44100


def test_all_user_visible_midi_audio_publishers_record_renderer_metadata() -> None:
    transcribe_source = inspect.getsource(capabilities.handle_transcribe)
    score_source = inspect.getsource(capabilities.handle_score)
    synthesize_source = inspect.getsource(capabilities.handle_synthesize)

    # Basic Pitch's non-empty WAV is known to come from the canonical renderer;
    # arbitrary future engine-supplied audio must not be mislabeled FluidSynth.
    assert 'result.provenance.engine == "basic_pitch"' in transcribe_source
    assert 'metadata={"renderer": render_metadata} if render_metadata else {}' in transcribe_source

    assert '"renderer": _midi_renderer_metadata()' in score_source
    assert 'metadata={"renderer": _midi_renderer_metadata(sr)}' in synthesize_source


def test_synthesize_docstring_no_longer_claims_removed_numpy_fallback() -> None:
    source = inspect.getsource(capabilities.handle_synthesize)
    assert "numpy fallback" not in source.lower()
