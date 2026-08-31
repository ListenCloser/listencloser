"""Generate visual and audio comparison between Basic Pitch and Transkun on real-piano.m4a.

Run: python -m scripts.compare_transcription_engines
"""

from __future__ import annotations

import io
from pathlib import Path

import pretty_midi

from music_features import (
    transcribe_with_engine,
)

FIXTURE_PATH = Path("/Users/giancarloricci/listencloser/tests/fixtures/real-piano.m4a")
OUTPUT_DIR = Path("/Users/giancarloricci/listencloser/backend/evaluation/reports/engine_comparison")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def _analyze_midi(midi_bytes: bytes) -> dict:
    """Analyze MIDI for comparison metrics."""
    pm = pretty_midi.PrettyMIDI(io.BytesIO(midi_bytes))
    notes = []
    for inst in pm.instruments:
        if inst.is_drum:
            continue
        for n in inst.notes:
            notes.append(n)

    if not notes:
        return {}

    pitches = [n.pitch for n in notes]
    durations = [n.end - n.start for n in notes]
    velocities = [n.velocity for n in notes]

    # Short notes (< 150ms)
    short_count = sum(1 for d in durations if d < 0.15)

    # High register notes (>= MIDI 86)
    high_reg = sum(1 for p in pitches if p >= 86)

    # Max polyphony (simplified: max notes overlapping at any point)
    events = []
    for n in notes:
        events.append((n.start, 1))
        events.append((n.end, -1))
    events.sort()
    current = 0
    max_poly = 0
    for _, delta in events:
        current += delta
        max_poly = max(max_poly, current)

    # Isolated high-register notes: high notes not overlapped by other notes
    isolated_high = 0
    for n in notes:
        if n.pitch >= 86:
            overlapped = False
            for m in notes:
                if m is n:
                    continue
                if m.start < n.end and m.end > n.start:
                    overlapped = True
                    break
            if not overlapped:
                isolated_high += 1

    return {
        "note_count": len(notes),
        "pitch_range": (min(pitches), max(pitches)),
        "short_notes": short_count,
        "high_register_notes": high_reg,
        "isolated_high_register": isolated_high,
        "max_polyphony": max_poly,
        "avg_velocity": sum(velocities) / len(velocities),
        "total_duration": max(n.end for n in notes) if notes else 0,
        "avg_note_duration": sum(durations) / len(durations) if durations else 0,
    }


def _render_piano_roll(midi_bytes: bytes, out_path: Path, title: str) -> None:
    """Render piano roll as PNG."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    pm = pretty_midi.PrettyMIDI(io.BytesIO(midi_bytes))
    piano_roll = pm.get_piano_roll(fs=100)

    fig, ax = plt.subplots(figsize=(14, 4))
    ax.imshow(
        piano_roll,
        aspect="auto",
        origin="lower",
        cmap="hot",
        extent=[0, pm.get_end_time(), 0, 128],
    )
    ax.set_title(title)
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("MIDI Pitch")
    ax.set_ylim(21, 108)
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def _synthesize_playback(midi_bytes: bytes, out_path: Path) -> bool:
    """Synthesize MIDI to WAV using pretty_midi."""
    try:
        pm = pretty_midi.PrettyMIDI(io.BytesIO(midi_bytes))
        audio = pm.synthesize(fs=44100)
        import soundfile as sf

        sf.write(out_path, audio, 44100)
        return True
    except Exception as e:
        print(f"  Synthesis failed: {e}")
        return False


def main() -> None:
    audio_bytes = FIXTURE_PATH.read_bytes()
    print(f"Loaded {len(audio_bytes)} bytes from {FIXTURE_PATH}")

    results = {}

    # --- Basic Pitch pipeline ---
    print("\n=== Basic Pitch (general profile) ===")
    tr_bp = transcribe_with_engine(audio_bytes, profile="general")
    print(f"  Engine: {tr_bp['provenance']['engine']}")
    print(f"  Notes: {tr_bp['num_notes']}")
    print(f"  Routing: {tr_bp['provenance']['routing_reason']}")

    bp_midi = tr_bp["midi"]
    bp_stats = _analyze_midi(bp_midi)
    print(f"  Stats: {bp_stats}")

    print("  Rendering piano roll...")
    _render_piano_roll(bp_midi, OUTPUT_DIR / "basic_pitch_pianoroll.png", "Basic Pitch Piano Roll")

    print("  Synthesizing playback...")
    _synthesize_playback(bp_midi, OUTPUT_DIR / "basic_pitch_playback.wav")

    results["basic_pitch"] = {
        "provenance": tr_bp["provenance"],
        "stats": bp_stats,
    }

    # --- Transkun pipeline ---
    print("\n=== Transkun (solo_piano profile) ===")
    tr_tk = transcribe_with_engine(audio_bytes, profile="solo_piano")
    print(f"  Engine: {tr_tk['provenance']['engine']}")
    print(f"  Notes: {tr_tk['num_notes']}")
    print(f"  Routing: {tr_tk['provenance']['routing_reason']}")

    tk_midi = tr_tk["midi"]
    tk_stats = _analyze_midi(tk_midi)
    print(f"  Stats: {tk_stats}")

    print("  Rendering piano roll...")
    _render_piano_roll(tk_midi, OUTPUT_DIR / "transkun_pianoroll.png", "Transkun Piano Roll")

    print("  Synthesizing playback...")
    _synthesize_playback(tk_midi, OUTPUT_DIR / "transkun_playback.wav")

    results["transkun"] = {
        "provenance": tr_tk["provenance"],
        "stats": tk_stats,
    }

    # --- Summary ---
    print("\n=== COMPARISON SUMMARY ===")
    for name, data in results.items():
        s = data["stats"]
        print(f"  {name}:")
        print(f"    Notes: {s.get('note_count', 0)}")
        print(f"    Pitch range: {s.get('pitch_range', 'N/A')}")
        print(f"    Short notes (<150ms): {s.get('short_notes', 0)}")
        print(f"    High register (>=86): {s.get('high_register_notes', 0)}")
        print(f"    Isolated high register: {s.get('isolated_high_register', 0)}")
        print(f"    Max polyphony: {s.get('max_polyphony', 0)}")
        print(f"    Avg velocity: {s.get('avg_velocity', 0):.1f}")

    # Generate side-by-side HTML for easy viewing
    html = f"""<!DOCTYPE html>
<html>
<head>
<title>Transcription Engine Comparison</title>
<style>
body {{ font-family: system-ui, sans-serif; max-width: 1400px; margin: 0 auto; padding: 20px; }}
h1 {{ margin-bottom: 0.5rem; }}
h2 {{ margin-top: 2rem; }}
table {{ border-collapse: collapse; width: 100%; }}
td {{ vertical-align: top; padding: 10px; }}
img {{ max-width: 100%; height: auto; border: 1px solid #ddd; }}
.comparison-table {{ width: 100%; border-collapse: collapse; }}
.comparison-table th, .comparison-table td {{
        border: 1px solid #ddd; padding: 8px; text-align: left; }}
.comparison-table th {{ background: #f5f5f5; }}
</style>
</head>
<body>
<h1>Transcription Engine Comparison: real-piano.m4a</h1>
<p>Fixture: 54.5s solo piano (M4A)</p>

<h2>Piano Rolls (identical viewport: 0-55s, pitch 21-108)</h2>
<table><tr>
<td style="width:50%"><h3>Basic Pitch</h3><img src="basic_pitch_pianoroll.png"></td>
<td style="width:50%"><h3>Transkun</h3><img src="transkun_pianoroll.png"></td>
</tr></table>

<h2>Transcription Metrics</h2>
<table class="comparison-table">
<tr><th>Metric</th><th>Basic Pitch</th><th>Transkun</th></tr>
<tr><td>Engine</td><td>{results['basic_pitch']['provenance']['engine']}</td>
    <td>{results['transkun']['provenance']['engine']}</td></tr>
<tr><td>Profile</td><td>{results['basic_pitch']['provenance']['profile_requested']}</td>
    <td>{results['transkun']['provenance']['profile_requested']}</td></tr>
<tr><td>Routing</td><td>{results['basic_pitch']['provenance']['routing_reason']}</td>
    <td>{results['transkun']['provenance']['routing_reason']}</td></tr>
<tr><td>Raw note count</td><td>{results['basic_pitch']['stats'].get('note_count', 0)}</td>
    <td>{results['transkun']['stats'].get('note_count', 0)}</td></tr>
<tr><td>Pitch range</td><td>{results['basic_pitch']['stats'].get('pitch_range', 'N/A')}</td>
    <td>{results['transkun']['stats'].get('pitch_range', 'N/A')}</td></tr>
<tr><td>Short notes (<150ms)</td><td>{results['basic_pitch']['stats'].get('short_notes', 0)}</td>
    <td>{results['transkun']['stats'].get('short_notes', 0)}</td></tr>
<tr><td>High register notes (>=86)</td>
    <td>{results['basic_pitch']['stats'].get('high_register_notes', 0)}</td>
    <td>{results['transkun']['stats'].get('high_register_notes', 0)}</td></tr>
<tr><td>Isolated high register notes</td>
    <td>{results['basic_pitch']['stats'].get('isolated_high_register', 0)}</td>
    <td>{results['transkun']['stats'].get('isolated_high_register', 0)}</td></tr>
<tr><td>Max polyphony</td><td>{results['basic_pitch']['stats'].get('max_polyphony', 0)}</td>
    <td>{results['transkun']['stats'].get('max_polyphony', 0)}</td></tr>
<tr><td>Avg velocity</td><td>{results['basic_pitch']['stats'].get('avg_velocity', 0):.1f}</td>
    <td>{results['transkun']['stats'].get('avg_velocity', 0):.1f}</td></tr>
</table>

<h2>Synthesized Playback</h2>
<p><strong>Basic Pitch:</strong> <audio controls src="basic_pitch_playback.wav"></audio></p>
<p><strong>Transkun:</strong> <audio controls src="transkun_playback.wav"></audio></p>

<h2>Engine Provenance</h2>
<pre>Basic Pitch: {results['basic_pitch']['provenance']}</pre>
<pre>Transkun: {results['transkun']['provenance']}</pre>
</body>
</html>
"""
    (OUTPUT_DIR / "comparison.html").write_text(html)
    print(f"\n  Comparison HTML: {OUTPUT_DIR / 'comparison.html'}")
    print(f"  Output dir: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
