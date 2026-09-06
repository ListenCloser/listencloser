"""Produce canonical qualitative artifacts for a solo-piano fixture.

For each transcription engine result JSON, writes alongside the clip:
  <engine>_<clip>.mid   - predicted MIDI
  <engine>_<clip>.wav   - MIDI rendered to audio (same synth/settings for all engines)
  <engine>_<clip>.png   - piano-roll visualization (same settings for all engines)

Also prints the standard qualitative stats. This is diagnostic evidence only;
no F1 is computed (the fixtures have no reference MIDI).

Usage:
    python -m evaluation.analysis.qualitative_artifacts \
        <fixture_audio> <result_json>... [--out <dir>]
"""

from __future__ import annotations

import argparse
import base64
import json
from pathlib import Path

import numpy as np


def _notes_from_result(result: dict) -> list[dict]:
    return result.get("output", {}).get("notes", [])


def _midi_bytes_from_result(result: dict) -> bytes:
    raw = result.get("output", {}).get("midi")
    if raw is None:
        return b""
    # MIDI bytes are serialized as {"__base64__": "..."} by the bakeoff JSON
    # encoder so they round-trip losslessly without eval.
    if isinstance(raw, dict) and isinstance(raw.get("__base64__"), str):
        return base64.b64decode(raw["__base64__"])
    if isinstance(raw, bytes):
        return raw
    return b""


def _write_midi(midi_bytes: bytes, path: Path) -> None:
    path.write_bytes(midi_bytes)


def _render_wav(midi_path: Path, wav_path: Path, sample_rate: int = 44100) -> float:
    import pretty_midi

    pm = pretty_midi.PrettyMIDI(str(midi_path))
    audio = pm.synthesize(fs=sample_rate)
    import soundfile as sf

    sf.write(str(wav_path), audio.astype(np.float32), sample_rate)
    return len(audio) / sample_rate


def _piano_roll(midi_path: Path, png_path: Path, sample_rate: int = 44100) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import pretty_midi

    pm = pretty_midi.PrettyMIDI(str(midi_path))
    roll = pm.get_piano_roll(fs=sample_rate)
    fig, ax = plt.subplots(figsize=(14, 6))
    ax.imshow(roll, aspect="auto", origin="lower", cmap="viridis")
    ax.set_ylabel("MIDI pitch")
    ax.set_xlabel("time (s)")
    ax.set_title(f"{midi_path.stem} — piano roll ({pm.get_end_time():.1f}s)")
    ticks = np.linspace(0, roll.shape[1] - 1, 7, dtype=int)
    ax.set_xticks(ticks)
    ax.set_xticklabels([f"{t / sample_rate:.1f}" for t in ticks])
    fig.tight_layout()
    fig.savefig(str(png_path), dpi=110)
    plt.close(fig)


def _stats(result: dict, notes: list[dict]) -> dict:
    pitches = [int(n["pitch"]) for n in notes]
    durs = sorted(float(n["end"]) - float(n["start"]) for n in notes)
    onsets = sorted(float(n["start"]) for n in notes)
    max_poly = 0
    if notes:
        events = sorted(
            [(float(n["start"]), 1, int(n["pitch"])) for n in notes]
            + [(float(n["end"]), -1, int(n["pitch"])) for n in notes]
        )
        active = 0
        for _t, delta, _p in events:
            active += delta
            max_poly = max(max_poly, active)
    return {
        "note_count": len(notes),
        "pitch_range": (min(pitches), max(pitches)) if pitches else None,
        "notes_ge_midi86": sum(1 for p in pitches if p >= 86),
        "isolated_high_notes": sum(
            1
            for n in notes
            if int(n["pitch"]) >= 86
            and all(
                abs(float(n["start"]) - float(m["start"])) > 0.1
                or int(n["pitch"]) != int(m["pitch"])
                for m in notes
            )
        ),
        "short_notes_lt_150ms": sum(1 for d in durs if d < 0.15),
        "max_polyphony": max_poly,
        "duration": max(float(n["end"]) for n in notes) if notes else 0.0,
        "first_onset": onsets[0] if onsets else None,
        "runtime_s": result.get("runtime_s"),
        "status": "OK" if result.get("success") else "FAILED",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("fixture_audio", help="path to the fixture audio (real-piano.m4a)")
    parser.add_argument("result_json", nargs="+", help="engine result JSON files")
    parser.add_argument("--out", default=None, help="output directory (default: alongside results)")
    args = parser.parse_args()

    out_dir = Path(args.out) if args.out else Path(args.result_json[0]).resolve().parent
    out_dir.mkdir(parents=True, exist_ok=True)

    audio_dur = None
    try:
        import librosa

        audio, sr = librosa.load(args.fixture_audio, sr=None, mono=True)
        audio_dur = len(audio) / sr
    except Exception as exc:
        print(f"note: could not read fixture audio duration ({exc})")

    print(
        f"fixture: {args.fixture_audio} (duration={audio_dur:.2f}s)"
        if audio_dur
        else f"fixture: {args.fixture_audio}"
    )
    print("=" * 72)

    for json_path in args.result_json:
        with open(json_path) as f:
            result = json.load(f)
        engine = result["engine_name"]
        clip = result["clip_id"]
        notes = _notes_from_result(result)
        midi_bytes = _midi_bytes_from_result(result)

        stem = f"{engine}_{clip}"
        midi_path = out_dir / f"{stem}.mid"
        wav_path = out_dir / f"{stem}.wav"
        png_path = out_dir / f"{stem}.png"

        _write_midi(midi_bytes, midi_path)
        rendered = None
        try:
            rendered = _render_wav(midi_path, wav_path)
        except Exception as exc:
            print(f"render wav failed for {engine}: {exc}")
        try:
            _piano_roll(midi_path, png_path)
        except Exception as exc:
            print(f"piano roll failed for {engine}: {exc}")

        st = _stats(result, notes)
        print(f"[{engine}] {clip}  status={st['status']}")
        print(f"  artifacts: {midi_path.name}, {wav_path.name}, {png_path.name}")
        print(
            f"  notes={st['note_count']}  pitch_range={st['pitch_range']}  "
            f"notes>=MIDI86={st['notes_ge_midi86']}  short(<150ms)={st['short_notes_lt_150ms']}  "
            f"max_polyphony={st['max_polyphony']}"
        )
        print(
            f"  pred duration={st['duration']:.2f}s  first_onset={st['first_onset']}  "
            f"render_dur={rendered:.2f}s  runtime={st['runtime_s']}s"
        )
        print()


if __name__ == "__main__":
    main()
