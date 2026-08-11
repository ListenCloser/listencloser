"""Data models for the evaluation framework."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

ClipCategory = Literal[
    "solo_piano",
    "polyphonic_piano",
    "monophonic",
    "pitched_single_instrument",
    "melody_accompaniment",
    "full_mix",
    "noisy_recording",
]

ReferenceBeat = dict[str, Any]
ReferenceAnalysis = dict[str, Any]


@dataclass
class Reference:
    bpm: float | None = None
    key: str | None = None
    meter: str | None = None
    beats: list[float] = field(default_factory=list)
    downbeats: list[float] = field(default_factory=list)
    chords: list[dict[str, Any]] = field(default_factory=list)
    sections: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class EvalClip:
    id: str
    audio: str
    category: ClipCategory
    reference_midi: str | None = None
    reference_musicxml: str | None = None
    reference: Reference = field(default_factory=Reference)

    @classmethod
    def from_dict(cls, data: dict[str, Any], base_dir: str = "") -> EvalClip:
        ref_data = data.get("reference", {})
        return cls(
            id=data["id"],
            audio=f"{base_dir}/{data['audio']}" if base_dir else data["audio"],
            category=data["category"],
            reference_midi=(
                f"{base_dir}/{data['reference_midi']}"
                if base_dir and data.get("reference_midi")
                else data.get("reference_midi")
            ),
            reference_musicxml=(
                f"{base_dir}/{data['reference_musicxml']}"
                if base_dir and data.get("reference_musicxml")
                else data.get("reference_musicxml")
            ),
            reference=Reference(
                bpm=ref_data.get("bpm"),
                key=ref_data.get("key"),
                meter=ref_data.get("meter"),
                beats=ref_data.get("beats", []),
                downbeats=ref_data.get("downbeats", []),
                chords=ref_data.get("chords", []),
                sections=ref_data.get("sections", []),
            ),
        )


@dataclass
class CorpusManifest:
    clips: list[EvalClip]
    name: str = "unnamed"
    description: str = ""

    @classmethod
    def from_file(cls, path: str) -> CorpusManifest:
        import json
        import os

        base_dir = os.path.dirname(path)
        with open(path) as fh:
            data = json.load(fh)
        return cls(
            name=data.get("name", "unnamed"),
            description=data.get("description", ""),
            clips=[EvalClip.from_dict(c, base_dir) for c in data["clips"]],
        )
