"""Extract beat annotations from MAESTRO MIDI files.

MAESTRO MIDI files contain note events but not explicit beat annotations.
We can derive beat positions from the note onset density pattern, but this
is not a ground-truth beat annotation.

For now, we'll use the MIDI files to derive approximate beat positions
by looking at note onset density.
"""

from __future__ import annotations

import json
import os
from pathlib import Path


def extract_maestro_beats_from_midi(
    midi_dir: str,
    audio_dir: str,
    output_path: str,
    max_clips: int = 5,
) -> None:
    """Extract approximate beat annotations from MAESTRO MIDI files.

    Note: These are derived from note onset density, not ground-truth annotations.
    """
    import numpy as np
    import pretty_midi

    clips = []
    midi_files = sorted(Path(midi_dir).glob("*.midi"))[:max_clips]

    for midi_file in midi_files:
        clip_id = midi_file.stem
        audio_path = os.path.join(audio_dir, f"{clip_id}.wav")

        if not os.path.exists(audio_path):
            continue

        try:
            pm = pretty_midi.PrettyMIDI(str(midi_file))

            # Get all note onsets
            onsets = []
            for inst in pm.instruments:
                for note in inst.notes:
                    onsets.append(note.start)

            if not onsets:
                continue

            onsets = sorted(onsets)

            # Estimate tempo from onset intervals
            if len(onsets) >= 2:
                intervals = np.diff(onsets)
                intervals = intervals[intervals > 0]
                if len(intervals) > 0:
                    median_interval = np.median(intervals)
                    tempo = 60.0 / median_interval if median_interval > 0 else 120.0
                else:
                    tempo = 120.0
            else:
                tempo = 120.0

            # Generate beat positions at estimated tempo
            beat_interval = 60.0 / tempo
            duration = pm.get_end_time()
            beats = np.arange(0, duration, beat_interval).tolist()

            # Generate downbeats (every 4 beats for 4/4 time)
            downbeats = beats[::4]

            clips.append(
                {
                    "id": clip_id,
                    "audio_path": audio_path,
                    "dataset": "maestro",
                    "license": "CC BY-NC-SA 4.0",
                    "category": "solo_piano",
                    "description": "Classical piano performance",
                    "reference_bpm": round(tempo, 1),
                    "reference_beats": beats,
                    "reference_downbeats": downbeats,
                    "reference_meter_numerator": 4,
                    "reference_meter_denominator": 4,
                    "notes": "Beats derived from MIDI onset density, not ground-truth annotations",
                }
            )
        except Exception as e:
            print(f"  Error processing {clip_id}: {e}")

    manifest = {
        "name": "maestro_beats_derived",
        "description": "MAESTRO beat annotations derived from MIDI onset density",
        "source": "https://magenta.tensorflow.org/datasets/maestro",
        "license": "CC BY-NC-SA 4.0",
        "notes": (
            "Beats derived from MIDI onset density, not ground-truth. "
            "Use for diversity probing only."
        ),
        "clips": clips,
    }

    with open(output_path, "w") as f:
        json.dump(manifest, f, indent=2)

    print(f"Extracted {len(clips)} clips to {output_path}")


if __name__ == "__main__":
    import sys

    midi_dir = sys.argv[1] if len(sys.argv) > 1 else "backend/evaluation/.cache/maestro/midi"
    audio_dir = sys.argv[2] if len(sys.argv) > 2 else "backend/evaluation/.cache/maestro/audio"
    output_path = (
        sys.argv[3]
        if len(sys.argv) > 3
        else "backend/evaluation/analysis_v3/pulse/manifests/maestro_beats.json"
    )

    extract_maestro_beats_from_midi(midi_dir, audio_dir, output_path)
