import logging

import analyze


def test_midi_rhythm_logs_unexpected_failures(monkeypatch, caplog):
    def fail_to_parse(_path: str):
        raise RuntimeError("synthetic rhythm parser failure")

    monkeypatch.setattr(analyze.pretty_midi, "PrettyMIDI", fail_to_parse)

    with caplog.at_level(logging.ERROR, logger="analyze"):
        result = analyze._midi_rhythm("broken.mid")

    assert result is None
    assert "midi rhythm analysis failed" in caplog.text
    assert "synthetic rhythm parser failure" in caplog.text
