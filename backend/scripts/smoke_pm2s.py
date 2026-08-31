"""Exercise the baked PM2S checkpoints through the production notation adapter."""

from __future__ import annotations

import io

import pretty_midi

from engines.notation.pm2s_engine import PM2SNotationEngine


def _performance_midi() -> bytes:
    """Build a deterministic eight-bar two-hand piano performance."""
    midi = pretty_midi.PrettyMIDI(initial_tempo=120.0)
    piano = pretty_midi.Instrument(program=0, name="Piano")

    roots = (48, 53, 55, 48, 57, 53, 55, 48)
    right_hand = (60, 64, 67, 72)
    beat_seconds = 0.5

    for bar, root in enumerate(roots):
        bar_start = bar * 4 * beat_seconds
        for beat in range(4):
            # Keep a slight deterministic performance offset so PM2S sees a
            # performance-like sequence rather than already-quantized score MIDI.
            onset = bar_start + beat * beat_seconds + (0.012 if beat % 2 else 0.0)
            piano.notes.append(
                pretty_midi.Note(
                    velocity=78,
                    pitch=root + (7 if beat == 2 else 0),
                    start=onset,
                    end=onset + 0.43,
                )
            )
            for interval in (right_hand[beat], right_hand[(beat + 1) % len(right_hand)]):
                piano.notes.append(
                    pretty_midi.Note(
                        velocity=88,
                        pitch=interval + (bar % 2) * 2,
                        start=onset + 0.018,
                        end=onset + 0.38,
                    )
                )

    midi.instruments.append(piano)
    buffer = io.BytesIO()
    midi.write(buffer)
    return buffer.getvalue()


def main() -> None:
    performance_midi = _performance_midi()
    result = PM2SNotationEngine().convert(
        performance_midi,
        [],
        piano_grand_staff=True,
    )

    assert result.notation_midi.startswith(b"MThd")
    assert b"<score-partwise" in result.musicxml
    assert result.provenance.engine == "pm2s"
    assert result.quantization_report["input_notes"] > 0
    assert result.quantization_report["output_notes"] > 0
    assert result.quantization_report["musicxml_stage"] == "musescore_midi_import"
    print(
        "PM2S production smoke passed:",
        result.quantization_report["input_notes"],
        "input notes ->",
        result.quantization_report["output_notes"],
        "score notes",
    )


if __name__ == "__main__":
    main()
