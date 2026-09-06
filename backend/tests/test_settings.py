

@pytest.mark.parametrize("value", ["-0.1", "1.1", "many", ""])
def test_observability_settings_reject_invalid_trace_sample_rate(monkeypatch, value: str):
    monkeypatch.setenv("SENTRY_TRACES_SAMPLE_RATE", value)
    with pytest.raises(ValidationError):
        ObservabilitySettings()


def test_engine_settings_preserve_current_defaults():
    settings = EngineSettings()

    assert settings.transcription == "basic_pitch"
    assert settings.beat == "beat_this"
    assert settings.notation == "musescore"
    assert settings.harmony == "music21"
    assert settings.melody == "midibert"
    assert settings.theory == "theory_interpreter"


def test_engine_settings_read_deployment_overrides(monkeypatch):
    monkeypatch.setenv("TRANSCRIPTION_ENGINE", "transkun")
    monkeypatch.setenv("BEAT_ENGINE", "librosa")
    monkeypatch.setenv("NOTATION_ENGINE", "pm2s")
    monkeypatch.setenv("HARMONY_ENGINE", "lv_chordia")
    monkeypatch.setenv("MELODY_ENGINE", "skyline")
    monkeypatch.setenv("THEORY_ENGINE", "custom_theory")

    settings = EngineSettings()

    assert settings.transcription == "transkun"