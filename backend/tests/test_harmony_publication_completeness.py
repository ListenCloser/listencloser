from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import domain.capabilities as capabilities
from domain.models import Capability, Job


def test_handle_analyze_persists_complete_admitted_harmony_timeline(monkeypatch):
    input_version_id = uuid4()
    job = Job(
        workflow_id=uuid4(),
        capability=Capability(name="analyze", version="1.0"),
        input_version_ids=[input_version_id],
    )

    chords = [
        {"root": f"R{index}", "quality": "maj", "start": float(index), "end": float(index) + 0.5}
        for index in range(25)
    ]
    roman_numerals = [
        {
            "numeral": f"I{index}",
            "start": float(index),
            "end": float(index) + 0.5,
            "key_context": "C major",
        }
        for index in range(35)
    ]
    functions = [
        {
            "function": "tonic",
            "numeral": f"I{index}",
            "start": float(index),
            "end": float(index) + 0.5,
            "key_context": "C major",
        }
        for index in range(35)
    ]
    analysis = {
        "harmony_provenance": {"chords": {"engine": "lv-chordia"}},
        "chords": chords,
        "roman_numerals": [],
        "roman_numerals_theory": roman_numerals,
        "harmonic_functions": functions,
        "theory_provenance": {"engine": "theory_interpreter"},
        "cadences_theory": [],
        "key_regions_theory": [],
        "rhythm": {},
        "harmonic_rhythm": [],
        "melody": {},
    }

    monkeypatch.setattr(capabilities, "_resolve_owner_id", lambda _client, _workflow_id: "owner")
    monkeypatch.setattr(
        capabilities,
        "_lookup_version",
        lambda _client, _version_id: SimpleNamespace(id=input_version_id, metadata={}),
    )
    monkeypatch.setattr(capabilities, "download_version_bytes", lambda _version, _client: b"midi")
    monkeypatch.setattr(capabilities, "_update_progress", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        capabilities.analyze,
        "analyze_midi",
        lambda *_args, **_kwargs: analysis,
    )

    persisted_kinds: list[str] = []

    def create_insight(_client, _version_id, kind, *_args, **_kwargs):
        persisted_kinds.append(kind)
        return uuid4()

    monkeypatch.setattr(capabilities, "_create_insight", create_insight)

    capabilities.handle_analyze(job, MagicMock())

    assert persisted_kinds.count("chord") == 25
    assert persisted_kinds.count("roman_numeral") == 35
    assert persisted_kinds.count("harmonic_function") == 35
