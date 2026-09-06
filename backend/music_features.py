"""
Server-side music features: audio transcription + MIDI synthesis.

Modules:
    - transcribe_audio: arbitrary audio → MIDI (basic-pitch ML model)
    - midi_to_wav: render MIDI to WAV with FluidSynth + the bundled SoundFont
    - enhance_audio: denoise/declip/normalize via ffmpeg
    - convert_format: MIDI ↔ MusicXML via music21

Production MIDI rendering is fail-closed. A missing or broken FluidSynth runtime
must surface as an explicit derived-playback failure rather than silently
changing to a lower-fidelity repository-owned synthesizer.

Runs on CPU (Oracle always-free ARM VM). Suitable for short clips
(seconds to a couple minutes).
"""

from __future__ import annotations

import contextlib
import copy
import io
import logging
import os
import tempfile
from typing import Any

import numpy as np
import soundfile as sf

from audio_processing import decode_audio_to_wav as decode_audio_to_wav
from audio_processing import enhance_audio as enhance_audio

logger = logging.getLogger("music_features")

# Location of the bundled GM SoundFont used for synthesis.
SOUNDFONT_PATH = os.environ.get(
    "SOUNDFONT_PATH",
    "/usr/share/sounds/sf2/FluidR3_GM.sf2",
)

# Normalization
_MAX_NORMALIZE_GAIN = 10.0


# ---------------------------------------------------------------------------
# MIDI -> WAV (FluidSynth + SoundFont)
# ---------------------------------------------------------------------------
def _midi_to_wav_fluidsynth(midi_bytes: bytes, sr: int = 22050) -> bytes:
    """Render MIDI to WAV via FluidSynth using the configured SoundFont.

    Production rendering deliberately has no semantic fallback: deployment
    guarantees the renderer and SoundFont, so their absence is an operational
    error rather than permission to publish different-sounding audio under the
    same product label.
    """
    if not os.path.exists(SOUNDFONT_PATH):
        raise RuntimeError(f"FluidSynth SoundFont is unavailable: {SOUNDFONT_PATH}")

    try:
        import fluidsynth  # pyfluidsynth
    except Exception as exc:
        raise RuntimeError("FluidSynth Python runtime is unavailable") from exc

    with tempfile.TemporaryDirectory() as td:
        midi_path = os.path.join(td, "input.mid")
        wav_path = os.path.join(td, "input.wav")
        with open(midi_path, "wb") as f:
            f.write(midi_bytes)
        fs = fluidsynth.Synth(samplerate=float(sr))
        try:
            sfid = fs.sfload(SOUNDFONT_PATH)
            if sfid < 0:
                raise RuntimeError(f"FluidSynth failed to load SoundFont: {SOUNDFONT_PATH}")
            fs.program_select(0, sfid, 0, 0)  # bank 0, piano (prog 0)
            # Light reverb + chorus for a less dry, more natural render.
            fs.set_reverb(0.25, 0.4, 0.6, 0.12)
            fs.set_chorus(2, 0.04, 0.6, 4.0, 0)
            fs.midi2audio(midi_path, wav_path)
        finally:
            fs.delete()
        if not os.path.exists(wav_path):
            raise RuntimeError("FluidSynth completed without producing a WAV file")
        with open(wav_path, "rb") as f:
            raw = f.read()
        if not raw:
            raise RuntimeError("FluidSynth produced an empty WAV file")
        # Peak-normalize the rendered audio (FluidSynth output is quiet).
        return _normalize_wav(raw)


def _normalize_wav(wav_bytes: bytes, peak: float = 0.95) -> bytes:
    """Peak-normalize a 16-bit PCM WAV in memory (no extra deps)."""
    data, sr = sf.read(io.BytesIO(wav_bytes))
    max_abs = float(np.max(np.abs(data))) if data.size else 0.0
    if max_abs > 0.0:
        gain = min(peak / max_abs, _MAX_NORMALIZE_GAIN)
        data = np.clip(data * gain, -1.0, 1.0)
    buf = io.BytesIO()
    sf.write(buf, data, sr, format="WAV", subtype="PCM_16")
    return buf.getvalue()


def midi_to_wav(midi_bytes: bytes, sr: int = 22050) -> bytes:
    """Render MIDI bytes to 16-bit PCM WAV using the canonical FluidSynth path."""
    return _midi_to_wav_fluidsynth(midi_bytes, sr)


def measure_start_seconds(midi_bytes: bytes) -> list[float]:
    """Measure start times (seconds) for a MIDI file.

    Uses the same pretty_midi tempo/time-signature interpretation as
    :func:`midi_to_wav`, so these seconds line up with the synthesized audio
    timeline. Returns an empty list if measure boundaries cannot be derived.
    """
    import pretty_midi

    try:
        midi = pretty_midi.PrettyMIDI(io.BytesIO(midi_bytes))
        return [round(float(t), 3) for t in midi.get_downbeats()]
    except Exception:
        logger.warning("measure_start_seconds failed, no measure grid available")
        return []


# ---------------------------------------------------------------------------
# Format conversion (MIDI <-> MusicXML)
# ---------------------------------------------------------------------------
def convert_format(
    data: bytes,
    source: str,
    target: str,
    notation_ready: bool = False,
    piano_grand_staff: bool = False,
) -> bytes:
    """Convert between MIDI and MusicXML using music21.

    Args:
        data: Raw file bytes (MIDI or MusicXML).
        source: 'midi' or 'musicxml'.
        target: 'midi' or 'musicxml'.
        notation_ready: True when ``data`` is already quantized notation MIDI.
        piano_grand_staff: When converting MIDI -> MusicXML, engrave a piano
            grand staff (treble + bass staves) instead of a single staff.

    Returns:
        Converted file bytes.

    Raises:
        ValueError: If source/target combination is unsupported.
    """
    from music21 import converter

    if source == target:
        return data

    with tempfile.TemporaryDirectory() as td:
        ext = ".mid" if source == "midi" else ".xml"
        in_path = os.path.join(td, f"input{ext}")
        with open(in_path, "wb") as f:
            f.write(data)

        if piano_grand_staff and source == "midi" and target == "musicxml":
            from notation.staffing import grand_staff_from_midi

            score = grand_staff_from_midi(data)
        else:
            score = converter.parse(in_path)

            # MIDI performance timing is not notation.  Use a deliberate, bounded
            # grid before engraving rather than passing every micro-timing artifact
            # through to MusicXML.  This is still a draft score: the provenance/UI
            # must never claim publication-quality notation from AMT alone.
            if target == "musicxml" and not notation_ready:
                with contextlib.suppress(Exception):
                    score.quantize(
                        quarterLengthDivisors=(2, 3, 4, 6, 8, 12, 16),
                        processOffsets=True,
                        processDurations=True,
                        inPlace=True,
                    )
                with contextlib.suppress(Exception):
                    score.makeNotation(inPlace=True)

        # Emit a key signature only when music21's analysis is confident. A
        # low-confidence key (or a default C major fallback) must not fabricate
        # a signature the transcription did not actually support.
        if target == "musicxml":
            with contextlib.suppress(Exception):
                analyzed = score.analyze("key")
                corr = analyzed.correlationCoefficient
                if corr is not None and corr >= 0.8:
                    from music21 import key as _key_mod

                    signature = _key_mod.KeySignature(analyzed.sharps)
                    for part in score.parts:
                        first_measure = part.getElementsByClass("Measure")[0]
                        first_measure.insert(0, copy.deepcopy(signature))

        out_ext = ".mid" if target == "midi" else ".xml"
        out_path = os.path.join(td, f"output{out_ext}")
        fmt = "midi" if target == "midi" else "musicxml"
        score.write(fmt, fp=out_path)

        with open(out_path, "rb") as f:
            return f.read()


def estimate_beat_grid(wav_bytes: bytes) -> tuple[float, list[float]]:
    """Estimate tempo and beat positions from decoded source audio.

    This is intentionally a separate notation concern: performance MIDI stays
    untouched, while score reduction can use a grid derived from the recording.
    """
    import librosa

    audio, sr = sf.read(io.BytesIO(wav_bytes), always_2d=False)
    if getattr(audio, "ndim", 1) > 1:
        audio = np.mean(audio, axis=1)
    tempo, frames = librosa.beat.beat_track(
        y=np.asarray(audio, dtype=np.float32), sr=sr, trim=False
    )
    beats = librosa.frames_to_time(frames, sr=sr).tolist()
    return float(np.asarray(tempo).reshape(-1)[0]), [float(value) for value in beats]


def notation_midi_from_performance(
    midi_bytes: bytes,
    beat_times: list[float],
    subdivisions: int = 4,
) -> tuple[bytes, dict[str, int | float | str]]:
    """Create a beat-aligned notation MIDI without mutating performance MIDI.

    Each note onset and end is snapped only to subdivisions of *detected audio
    beats*. If the audio grid is unavailable, the function preserves timing and
    reports that honestly instead of inventing a 120-BPM score grid.
    """
    import pretty_midi

    midi = pretty_midi.PrettyMIDI(io.BytesIO(midi_bytes))
    report: dict[str, int | float | str] = {
        "profile": "beat_aligned_sixteenth_v1",
        "subdivisions_per_beat": subdivisions,
        "beat_count": len(beat_times),
        "quantized_notes": 0,
        "timing_mode": "audio_beats" if len(beat_times) >= 2 else "preserved_no_grid",
    }
    if len(beat_times) < 2:
        out = io.BytesIO()
        midi.write(out)
        return out.getvalue(), report

    intervals = np.diff(np.asarray(beat_times, dtype=float))
    median_interval = float(np.median(intervals[intervals > 0])) if np.any(intervals > 0) else 0.5
    grid: list[float] = []
    for index, beat in enumerate(beat_times):
        next_beat = beat_times[index + 1] if index + 1 < len(beat_times) else beat + median_interval
        for division in range(subdivisions):
            grid.append(beat + (next_beat - beat) * division / subdivisions)
    grid.append(beat_times[-1] + median_interval)

    def nearest(value: float) -> float:
        index = int(np.searchsorted(grid, value))
        candidates = grid[max(0, index - 1) : min(len(grid), index + 1)]
        return (
            min(candidates, key=lambda candidate: abs(candidate - value)) if candidates else value
        )

    for instrument in midi.instruments:
        if instrument.is_drum:
            continue
        for note in instrument.notes:
            start = nearest(note.start)
            end = nearest(note.end)
            if end <= start:
                end = start + median_interval / subdivisions
            if start != note.start or end != note.end:
                report["quantized_notes"] = int(report["quantized_notes"]) + 1
            note.start, note.end = start, end
        instrument.notes.sort(key=lambda note: (note.start, note.pitch, note.end))
    out = io.BytesIO()
    midi.write(out)
    return out.getvalue(), report


# ---------------------------------------------------------------------------
# MIDI post-processing (noise reduction)
# ---------------------------------------------------------------------------
_MIN_NOTE_DURATION = 0.075
_MIN_PIANO_PITCH = 21
_MAX_PIANO_PITCH = 108
_LOW_VELOCITY = 18
_LOW_VELOCITY_SHORT_DURATION = 0.16


def _clean_midi(midi_bytes: bytes) -> tuple[bytes, dict[str, int | str]]:
    """Apply conservative *performance* cleanup and report every decision.

    This deliberately does not quantize timing. Basic Pitch's output is a
    performance hypothesis; snapping it before beat/downbeat alignment can
    make a correct expressive onset wrong. A later notation-only pipeline will
    consume this artifact and apply an explicit beat-aligned grid.
    """
    import pretty_midi as pm

    midi = pm.PrettyMIDI(io.BytesIO(midi_bytes))

    report: dict[str, int | str] = {
        "profile": "performance_conservative_v1",
        "input_notes": 0,
        "kept_notes": 0,
        "removed_short": 0,
        "removed_low_velocity": 0,
        "removed_out_of_range": 0,
        "merged_overlaps": 0,
    }
    for inst in midi.instruments:
        if inst.is_drum:
            continue
        report["input_notes"] = int(report["input_notes"]) + len(inst.notes)
        filtered = []
        for note in inst.notes:
            duration = note.end - note.start
            if note.pitch < _MIN_PIANO_PITCH or note.pitch > _MAX_PIANO_PITCH:
                report["removed_out_of_range"] = int(report["removed_out_of_range"]) + 1
            elif duration < _MIN_NOTE_DURATION:
                report["removed_short"] = int(report["removed_short"]) + 1
            elif note.velocity < _LOW_VELOCITY and duration < _LOW_VELOCITY_SHORT_DURATION:
                report["removed_low_velocity"] = int(report["removed_low_velocity"]) + 1
            else:
                filtered.append(note)
        # Merge same-pitch overlaps; preserve the earliest onset and longest end.
        inst.notes = filtered
        inst.notes.sort(key=lambda n: (n.pitch, n.start))
        cleaned = []
        for note in inst.notes:
            if not cleaned or note.pitch != cleaned[-1].pitch or note.start >= cleaned[-1].end:
                cleaned.append(note)
            else:
                cleaned[-1].end = max(cleaned[-1].end, note.end)
                cleaned[-1].velocity = max(cleaned[-1].velocity, note.velocity)
                report["merged_overlaps"] = int(report["merged_overlaps"]) + 1
        inst.notes = cleaned
        report["kept_notes"] = int(report["kept_notes"]) + len(inst.notes)

    buf = io.BytesIO()
    midi.write(buf)
    return buf.getvalue(), report


# ---------------------------------------------------------------------------
# Audio -> MIDI (basic-pitch)
# ---------------------------------------------------------------------------
def transcribe_audio(
    audio_bytes: bytes,
    fmt: str = "wav",
    onset_threshold: float = 0.5,
    frame_threshold: float = 0.3,
) -> dict:
    """Transcribe audio to MIDI. Returns a dict with midi (bytes), wav (bytes),
    notes (list of {pitch, start, end, velocity, amplitude}), model_note_events
    (the raw Basic Pitch note events with per-note amplitude), and duration_s.

    Expects clean WAV (callers run enhance_audio first)."""
    from basic_pitch.inference import predict

    safe_fmt = fmt.lower().lstrip(".")
    if safe_fmt not in {"wav", "mp3", "m4a", "flac", "ogg", "aac"}:
        safe_fmt = "wav"

    with tempfile.TemporaryDirectory() as td:
        in_path = os.path.join(td, f"input.{safe_fmt}")
        with open(in_path, "wb") as f:
            f.write(audio_bytes)
        # basic-pitch writes <input_stem>.mid + note events to out_dir.
        out_dir = os.path.join(td, "out")
        os.makedirs(out_dir, exist_ok=True)
        _model_output, midi_data, note_events = predict(
            in_path,
            onset_threshold=onset_threshold,
            frame_threshold=frame_threshold,
        )
        midi_path = os.path.join(out_dir, "input.mid")
        midi_data.write(midi_path)
        with open(midi_path, "rb") as f:
            midi_bytes = f.read()

    # Basic Pitch's per-note evidence: (start_s, end_s, pitch_midi, amplitude,
    # pitch_bends). ``amplitude`` is the mean note-frame activation in [0, 1] —
    # the model's per-note "presence" score, NOT a calibrated probability. The
    # MIDI velocity is Basic Pitch's own ``round(127 * amplitude)`` rounding.
    model_note_events = [
        {
            "start": float(start),
            "end": float(end),
            "pitch": int(pitch),
            "amplitude": float(amplitude),
            "pitch_bends": [int(b) for b in pitch_bends] if pitch_bends else None,
        }
        for (start, end, pitch, amplitude, pitch_bends) in note_events
    ]

    # Post-process MIDI: remove noise, normalize velocities
    try:
        midi_bytes, cleanup_report = _clean_midi(midi_bytes)
    except Exception as e:
        logger.warning(f"MIDI cleanup failed, using raw output: {e}")
        cleanup_report = {"profile": "raw_basic_pitch_fallback", "input_notes": 0, "kept_notes": 0}

    # Persist the notes in the final cleaned MIDI so every representation agrees.
    import pretty_midi

    cleaned_midi = pretty_midi.PrettyMIDI(io.BytesIO(midi_bytes))
    # Match canonical notes back to their model evidence.  The MIDI round-trip
    # quantizes onsets to ticks (~0.5 ms), so greedy-match by pitch + nearest
    # onset within a 20 ms tolerance.
    events_by_pitch: dict[int, list[dict]] = {}
    for ev in model_note_events:
        events_by_pitch.setdefault(ev["pitch"], []).append(ev)
    for evs in events_by_pitch.values():
        evs.sort(key=lambda e: e["start"])
    used: set[int] = set()
    notes = []
    for instrument in cleaned_midi.instruments:
        for note in instrument.notes:
            if instrument.is_drum:
                continue
            amplitude = None
            best = None
            best_d = 20e-3
            for ev in events_by_pitch.get(note.pitch, []):
                if id(ev) in used:
                    continue
                d = abs(ev["start"] - note.start)
                if d < best_d:
                    best_d = d
                    best = ev
            if best is not None:
                used.add(id(best))
                amplitude = best["amplitude"]
            notes.append(
                {
                    "pitch": note.pitch,
                    "start": note.start,
                    "end": note.end,
                    "velocity": note.velocity,
                    "amplitude": amplitude,
                }
            )

    wav_bytes = midi_to_wav(midi_bytes)
    return {
        "midi": midi_bytes,
        "wav": wav_bytes,
        "notes": notes,
        "num_notes": len(notes),
        "cleanup_report": cleanup_report,
        "model_note_events": model_note_events,
    }


# ---------------------------------------------------------------------------
# Engine-aware wrappers — resolve engines via registry at runtime.
# The implementations above remain as helpers; the wrappers below are the
# canonical public API for caller sites that want provenance-aware results.
# ---------------------------------------------------------------------------


def transcribe_with_engine(
    audio_bytes: bytes,
    fmt: str = "wav",
    onset_threshold: float = 0.5,
    frame_threshold: float = 0.3,
    profile: str | None = None,
) -> dict:
    """Transcribe audio using the configured transcription engine.

    Args:
        audio_bytes: Audio data.
        fmt: Audio format.
        onset_threshold: Onset threshold for engines that support it.
        frame_threshold: Frame threshold for engines that support it.
        profile: Transcription profile: "solo_piano" -> transkun, "general"/"auto" -> basic_pitch.

    Uses the global registry default engine. Durable jobs that need a
    per-job engine selection call :func:`get_transcription_engine_for_job`
    instead (see ``handle_transcribe``), so requirement handlers never bypass
    the engine seam.

    Returns the same dict as transcribe_audio, with 'provenance' added.
    """
    from engines.registry import get_transcription_engine

    engine = get_transcription_engine(
        profile=profile,
        onset_threshold=onset_threshold,
        frame_threshold=frame_threshold,
    )
    result = engine.transcribe(audio_bytes, fmt=fmt)
    prov = result.provenance.to_dict()
    base = {
        "midi": result.midi,
        "wav": result.wav,
        "notes": result.notes,
        "num_notes": result.num_notes,
        "cleanup_report": result.cleanup_report,
        "model_note_events": result.model_note_events,
        "tempo_is_placeholder": result.tempo_is_placeholder,
        "meter_is_placeholder": result.meter_is_placeholder,
        "supports_meter": result.supports_meter,
        "provenance": prov,
    }
    return base


def get_transcription_engine_for_job(
    name: str | None = None,
    profile: str | None = None,
    onset_threshold: float = 0.5,
    frame_threshold: float = 0.3,
):
    """Resolve a transcription engine for a durable job.

    When name is provided, use it directly. Otherwise falls back to
    TRANSCRIPTION_ENGINE env var or 'basic_pitch' default.
    """
    from engines.registry import get_transcription_engine

    return get_transcription_engine(
        name=name,
        profile=profile,
        onset_threshold=onset_threshold,
        frame_threshold=frame_threshold,
    )


def estimate_beats_with_engine(wav_bytes: bytes, engine_name: str | None = None) -> dict:
    """Estimate beats using a beat engine.

    When ``engine_name`` is provided it overrides the configured default
    (``BEAT_ENGINE``); otherwise the shared default engine is used. This lets
    the Analysis path opt into a specialist beat tracker (beat_this) without
    changing the engine used by Score/notation.

    Returns a dict with bpm, beats, downbeats (may be None), and provenance.
    """
    from engines.registry import get_beat_engine

    engine = get_beat_engine(name=engine_name)
    result = engine.analyze(wav_bytes)
    return {
        "bpm": result.bpm,
        "beats": result.beats,
        "downbeats": result.downbeats,
        "provenance": result.provenance.to_dict(),
    }


def notation_with_engine(
    midi_bytes: bytes,
    beat_times: list[float],
    *,
    engine_name: str | None = None,
    **kwargs: Any,
) -> dict:
    """Create notation using an explicit or configured notation engine.

    Returns a dict with notation_midi, musicxml, quantization_report, and provenance.
    Keyword arguments are forwarded to the engine's convert method (e.g. adaptive,
    downbeats, beat_positions, notation_ready, piano_grand_staff).
    """
    from engines.registry import get_notation_engine

    engine = get_notation_engine(engine_name)
    result = engine.convert(midi_bytes, beat_times, **kwargs)
    return {
        "notation_midi": result.notation_midi,
        "musicxml": result.musicxml,
        "quantization_report": result.quantization_report,
        "provenance": result.provenance.to_dict(),
    }


def adaptive_notation_from_performance(
    midi_bytes: bytes,
    beats: list[float],
    downbeats: list[float] | None = None,
    beat_positions: list[int] | None = None,
) -> tuple[bytes, dict[str, Any]]:
    """Create notation MIDI using adaptive measure-aware quantization.

    Unlike notation_midi_from_performance (fixed subdivisions), this builds a
    metrical grid from beat/downbeat positions and selects per-measure candidate
    grids. Performance MIDI is never mutated.

    Returns (notation_midi_bytes, quantization_report_dict).
    """
    from notation.grid import build_metrical_grid
    from notation.quantize import adaptive_quantize, quantize_rhythmic_grid

    grid = build_metrical_grid(beats, downbeats, beat_positions)
    notation_midi, report = adaptive_quantize(midi_bytes, grid)
    report["grid"] = grid.to_dict()

    # When beat/downbeat tracking is unavailable (or inconsistent with the
    # MIDI's own tempo), fall back to evidence-based rhythmic grid selection so
    # the notation uses musically plausible note values rather than raw
    # performance micro-timing.
    if report.get("timing_mode") in (None, "preserved_no_grid", "preserved_no_meter"):
        notation_midi, report = quantize_rhythmic_grid(midi_bytes)
        report["grid"] = grid.to_dict()

    return notation_midi, report
