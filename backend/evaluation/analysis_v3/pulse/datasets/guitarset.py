"""Extract beat annotations from GuitarSet JAMS files."""

from __future__ import annotations

import json
import os
from pathlib import Path


def extract_guitarset_annotations(
    annotation_dir: str,
    audio_dir: str,
    output_path: str,
) -> None:
    """Extract beat annotations from GuitarSet JAMS files."""
    import jams

    clips = []
    for jams_file in sorted(Path(annotation_dir).glob("*.jams")):
        clip_id = jams_file.stem
        audio_path = os.path.join(audio_dir, f"{clip_id}_mic.wav")

        if not os.path.exists(audio_path):
            continue

        try:
            jam = jams.load(str(jams_file))

            beats = []
            downbeats = []
            tempo = None
            meter_numerator = None
            meter_denominator = None

            for ann in jam.annotations:
                if ann.namespace == "beat_position":
                    for obs in ann:
                        time = float(obs.time)
                        pos = obs.value.get("position", 0)
                        beats.append(time)
                        if pos == 1:
                            downbeats.append(time)
                        if meter_numerator is None:
                            meter_numerator = obs.value.get("num_beats", 4)
                            meter_denominator = obs.value.get("beat_units", 4)

                if ann.namespace == "tempo":
                    for obs in ann:
                        tempo = float(obs.value)
                        break

            if beats:
                clips.append(
                    {
                        "id": clip_id,
                        "audio_path": audio_path,
                        "dataset": "guitarset",
                        "license": "MIT",
                        "reference_beats": beats,
                        "reference_downbeats": downbeats if downbeats else None,
                        "reference_bpm": tempo,
                        "reference_meter_numerator": meter_numerator,
                        "reference_meter_denominator": meter_denominator,
                    }
                )
        except Exception as e:
            print(f"  Error processing {clip_id}: {e}")

    manifest = {
        "name": "guitarset_beat_annotations",
        "description": "GuitarSet beat/downbeat/tempo annotations",
        "source": "https://github.com/marl/GuitarSet",
        "license": "MIT",
        "clips": clips,
    }

    with open(output_path, "w") as f:
        json.dump(manifest, f, indent=2)

    print(f"Extracted {len(clips)} clips to {output_path}")


if __name__ == "__main__":
    import sys

    annotation_dir = (
        sys.argv[1] if len(sys.argv) > 1 else "backend/evaluation/.cache/guitarset/annotation"
    )
    audio_dir = sys.argv[2] if len(sys.argv) > 2 else "backend/evaluation/.cache/guitarset/audio"
    output_path = (
        sys.argv[3]
        if len(sys.argv) > 3
        else "backend/evaluation/analysis_v3/pulse/manifests/guitarset_beats.json"
    )

    extract_guitarset_annotations(annotation_dir, audio_dir, output_path)
