"""Data models for the evaluation framework."""

from __future__ import annotations

import os
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
    # Real-world dataset provenance / excerpt metadata (optional; synthetic
    # fixtures leave these unset).
    dataset: str | None = None
    split: str | None = None
    source_id: str | None = None
    license: str | None = None
    audio_provenance: str | None = None
    metrics: list[str] = field(default_factory=list)
    excerpt_start: float | None = None
    excerpt_end: float | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any], base_dir: str = "") -> EvalClip:
        ref_data = data.get("reference", {})

        # Support environment variable substitution in paths: ${VAR}/path or ${VAR}
        def resolve_path(path: str | None) -> str | None:
            if path is None:
                return None
            if path.startswith("${"):
                # Handle ${VAR}/rest or ${VAR}
                end = path.find("}")
                if end != -1:
                    env_var = path[2:end]
                    rest = path[end + 1 :]
                    expanded = os.environ.get(env_var, "")
                    if expanded:
                        return expanded + rest
            return f"{base_dir}/{path}" if base_dir and not os.path.isabs(path) else path

        return cls(
            id=data["id"],
            audio=resolve_path(data.get("audio")),
            category=data.get("category", "unknown"),
            reference_midi=resolve_path(data.get("reference_midi")),
            reference_musicxml=resolve_path(data.get("reference_musicxml")),
            reference=Reference(
                bpm=ref_data.get("bpm"),
                key=ref_data.get("key"),
                meter=ref_data.get("meter"),
                beats=ref_data.get("beats", []),
                downbeats=ref_data.get("downbeats", []),
                chords=ref_data.get("chords", []),
                sections=ref_data.get("sections", []),
            ),
            dataset=data.get("dataset"),
            split=data.get("split"),
            source_id=data.get("source_id"),
            license=data.get("license"),
            audio_provenance=data.get("audio_provenance"),
            metrics=data.get("metrics", []),
            excerpt_start=data.get("excerpt_start"),
            excerpt_end=data.get("excerpt_end"),
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
