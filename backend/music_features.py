"""
Server-side music features: audio transcription + MIDI synthesis.

Modules:
    - transcribe_audio: arbitrary audio → MIDI (basic-pitch ML model)
    - midi_to_wav: render MIDI to WAV (FluidSynth with SoundFont, numpy fallback)
    - enhance_audio: denoise/declip/normalize via ffmpeg
    - convert_format: MIDI ↔ MusicXML via music21

Fallback strategy:
    FluidSynth (natural timbre) → numpy additive synth (portable fallback)
    Both produce 16-bit PCM WAV at 22050 Hz.

Runs on CPU (Oracle always-free ARM VM). Suitable for short clips
(seconds to a couple minutes).
"""

import contextlib
import io
import logging
import os
import subprocess
import tempfile

import numpy as np
import soundfile as sf

logger = logging.getLogger("music_features")

# Location of the bundled GM SoundFont used for synthesis.
SOUNDFONT_PATH = os.environ.get(
    "SOUNDFONT_PATH",
    "/usr/share/sounds/sf2/FluidR3_GM.sf2",
)

# Subprocess timeout (seconds)
_FFMPEG_TIMEOUT = 120

# Normalization
_MAX_NORMALIZE_GAIN = 10.0

# Numpy synth constants
_SYNTH_EXTRA_DURATION = 0.5
_SYNTH_MIN_NOTE_DURATION = 0.2
_SYNTH_ATTACK_TIME = 0.01
_SYNTH_RELEASE_TIME = 0.15
_SYNTH_HARMONICS = [(1, 1.0), (2, 0.3), (3, 0.12), (4, 0.06)]
_SYNTH_AMPLITUDE = 0.22


# ---------------------------------------------------------------------------
# MIDI -> WAV (FluidSynth + SoundFont, numpy fallback)
# ---------------------------------------------------------------------------
def _midi_to_wav_fluidsynth(midi_bytes: bytes, sr: int = 22050) -> bytes | None:
    """Render MIDI to WAV via FluidSynth using a bundled SoundFont.

    Returns None if FluidSynth or the SoundFont is unavailable so the caller can
    fall back to the numpy synth.
    """
    if not os.path.exists(SOUNDFONT_PATH):
        return None
    try:
        import fluidsynth  # pyfluidsynth
    except Exception as e:
        logger.warning(f"fluidsynth unavailable, falling back to numpy synth: {e}")
        return None

    with tempfile.TemporaryDirectory() as td:
        midi_path = os.path.join(td, "input.mid")
        wav_path = os.path.join(td, "input.wav")
        with open(midi_path, "wb") as f:
            f.write(midi_bytes)
        fs = fluidsynth.Synth(samplerate=float(sr))
        try:
            sfid = fs.sfload(SOUNDFONT_PATH)
            fs.program_select(0, sfid, 0, 0)  # bank 0, piano (prog 0)
            # Light reverb + chorus for a less dry, more natural render.
            fs.set_reverb(0.25, 0.4, 0.6, 0.12)
            fs.set_chorus(2, 0.04, 0.6, 4.0, 0)
            fs.midi2audio(midi_path, wav_path)
        finally:
            fs.delete()
        if not os.path.exists(wav_path):
            return None
        with open(wav_path, "rb") as f:
            raw = f.read()
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


def _note_to_freq(midi_note: int) -> float:
    return 440.0 * (2.0 ** ((midi_note - 69) / 12.0))


def _midi_to_wav_numpy(midi_bytes: bytes, sr: int = 22050) -> bytes:
    """Self-contained polyphonic piano synth (additive sines + ADSR)."""
    import pretty_midi

    midi = pretty_midi.PrettyMIDI(io.BytesIO(midi_bytes))
    duration = max(midi.get_end_time(), 0.1)
    n = int((duration + _SYNTH_EXTRA_DURATION) * sr)
    out = np.zeros(n, dtype=np.float64)

    for instrument in midi.instruments:
        for note in instrument.notes:
            f = _note_to_freq(note.pitch)
            start = int(note.start * sr)
            end = int(note.end * sr)
            if end <= start:
                end = start + int(_SYNTH_MIN_NOTE_DURATION * sr)
            seg = np.arange(end - start) / sr
            env = np.ones_like(seg)
            attack = int(_SYNTH_ATTACK_TIME * sr)
            release = int(_SYNTH_RELEASE_TIME * sr)
            if len(env) > attack:
                env[:attack] = np.linspace(0, 1, attack)
            if len(env) > release:
                env[-release:] = np.linspace(1, 0, release)
            sig = np.zeros_like(seg)
            for mult, amp in _SYNTH_HARMONICS:
                sig += amp * np.sin(2 * np.pi * f * mult * seg)
            sig *= env * _SYNTH_AMPLITUDE
            out[start:end] += sig

    out = np.clip(out, -1.0, 1.0)
    pcm = (out * 32767.0).astype(np.int16)
    buf = io.BytesIO()
    sf.write(buf, pcm, sr, format="WAV", subtype="PCM_16")
    return buf.getvalue()


def midi_to_wav(midi_bytes: bytes, sr: int = 22050) -> bytes:
    """Render MIDI bytes to a 16-bit PCM WAV. Prefers FluidSynth (natural
    timbre) and falls back to the numpy synth if unavailable."""
    wav = _midi_to_wav_fluidsynth(midi_bytes, sr)
    if wav is not None:
        return wav
    return _midi_to_wav_numpy(midi_bytes, sr)


# ---------------------------------------------------------------------------
# Audio cleanup (ffmpeg pipeline, hidden preprocessing step)
# ---------------------------------------------------------------------------
_ALLOWED_AUDIO_FORMATS = frozenset({".wav", ".flac", ".ogg", ".mp3", ".m4a", ".aac", ".webm"})


def _sanitize_fmt(fmt: str) -> str:
    ext = fmt if fmt.startswith(".") else f".{fmt}"
    return ext if ext in _ALLOWED_AUDIO_FORMATS else ".wav"


def enhance_audio(audio_bytes: bytes, fmt: str = "wav") -> bytes:
    """Light, CPU-friendly cleanup of a raw recording: denoise (afftdn),
    declip (adeclip), and EBU R128 normalize (loudnorm). Returns cleaned WAV.

    Runs transparently before transcription so every upload/recording is
    cleaned without the user opting in. No-op safe: returns input if ffmpeg
    is unavailable or the pipeline fails.
    """
    suffix = _sanitize_fmt(fmt)
    with tempfile.TemporaryDirectory() as td:
        in_path = os.path.join(td, f"input{suffix}")
        with open(in_path, "wb") as f:
            f.write(audio_bytes)
        src = in_path
        # basic-pitch only reads wav/flac/ogg/mp3; convert other formats first.
        if suffix not in (".wav", ".flac", ".ogg", ".mp3", ".m4a", ".aac"):
            conv = subprocess.run(
                [
                    "ffmpeg",
                    "-y",
                    "-i",
                    src,
                    "-ac",
                    "1",
                    "-ar",
                    "22050",
                    os.path.join(td, "input_conv.wav"),
                ],
                capture_output=True,
                timeout=_FFMPEG_TIMEOUT,
            )
            if conv.returncode != 0 or not os.path.exists(os.path.join(td, "input_conv.wav")):
                logger.warning("enhance: pre-convert failed, using raw input")
                return audio_bytes
            src = os.path.join(td, "input_conv.wav")
        out_path = os.path.join(td, "clean.wav")
        cmd = [
            "ffmpeg",
            "-y",
            "-i",
            src,
            "-af",
            "afftdn=nr=12:nf=-30,adeclip,loudnorm=I=-16:TP=-1.5:LRA=11",
            "-ar",
            "22050",
            "-ac",
            "1",
            out_path,
        ]
        res = subprocess.run(cmd, capture_output=True, timeout=120)
        if res.returncode != 0 or not os.path.exists(out_path):
            logger.warning("enhance pipeline failed, using source: " + res.stderr.decode()[:200])
            # Fall back to the (already converted) source if cleanup failed.
            if src != in_path:
                with open(src, "rb") as f:
                    return f.read()
            return audio_bytes
        with open(out_path, "rb") as f:
            return f.read()


def decode_audio_to_wav(audio_bytes: bytes, fmt: str = "wav") -> bytes:
    """Decode a supported upload into a validated mono PCM WAV."""
    suffix = _sanitize_fmt(fmt)
    with tempfile.TemporaryDirectory() as td:
        input_path = os.path.join(td, f"input{suffix}")
        output_path = os.path.join(td, "decoded.wav")
        with open(input_path, "wb") as file_handle:
            file_handle.write(audio_bytes)
        try:
            result = subprocess.run(
                [
                    "ffmpeg",
                    "-v",
                    "error",
                    "-y",
                    "-i",
                    input_path,
                    "-ac",
                    "1",
                    "-ar",
                    "22050",
                    "-c:a",
                    "pcm_s16le",
                    output_path,
                ],
                capture_output=True,
                timeout=_FFMPEG_TIMEOUT,
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            raise ValueError("Audio decoding failed") from error
        if result.returncode != 0 or not os.path.exists(output_path):
            detail = result.stderr.decode(errors="replace")[-300:]
            raise ValueError(f"Audio decoding failed: {detail or 'invalid audio file'}")
        with open(output_path, "rb") as file_handle:
            decoded = file_handle.read()
        if not decoded.startswith(b"RIFF") or len(decoded) < 44:
            raise ValueError("Audio decoding produced an invalid WAV")
        return decoded


# ---------------------------------------------------------------------------
# Format conversion (MIDI <-> MusicXML)
# ---------------------------------------------------------------------------
def convert_format(data: bytes, source: str, target: str) -> bytes:
    """Convert between MIDI and MusicXML using music21.

    Args:
        data: Raw file bytes (MIDI or MusicXML).
        source: 'midi' or 'musicxml'.
        target: 'midi' or 'musicxml'.

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

        score = converter.parse(in_path)

        # Quantize to 16th note grid for cleaner notation
        if target == "musicxml":
            with contextlib.suppress(Exception):
                score.quantize(inPlace=True)

        out_ext = ".mid" if target == "midi" else ".xml"
        out_path = os.path.join(td, f"output{out_ext}")
        fmt = "midi" if target == "midi" else "musicxml"
        score.write(fmt, fp=out_path)

        with open(out_path, "rb") as f:
            return f.read()


# ---------------------------------------------------------------------------
# MIDI post-processing (noise reduction)
# ---------------------------------------------------------------------------
_MIN_NOTE_DURATION = 0.05  # Remove notes shorter than 50ms


def _clean_midi(midi_bytes: bytes) -> bytes:
    """Post-process MIDI to remove noise and improve quality.

    Pipeline:
    1. Remove short spurious notes (< 50ms)
    2. Remove duplicate/overlapping notes at same pitch
    3. Normalize velocities to 0-127 range
    """
    import pretty_midi as pm

    midi = pm.PrettyMIDI(io.BytesIO(midi_bytes))

    for inst in midi.instruments:
        if inst.is_drum:
            continue
        # 1. Remove short notes
        inst.notes = [n for n in inst.notes if (n.end - n.start) >= _MIN_NOTE_DURATION]
        # 2. Remove duplicate/overlapping notes
        inst.notes.sort(key=lambda n: (n.pitch, n.start))
        cleaned = []
        for note in inst.notes:
            if not cleaned or note.pitch != cleaned[-1].pitch or note.start >= cleaned[-1].end:
                cleaned.append(note)
            else:
                cleaned[-1].end = max(cleaned[-1].end, note.end)
        inst.notes = cleaned
        # 3. Normalize velocities
        if inst.notes:
            max_vel = max(n.velocity for n in inst.notes)
            if max_vel > 0:
                for note in inst.notes:
                    note.velocity = int(note.velocity * 127 / max_vel)

    buf = io.BytesIO()
    midi.write(buf)
    return buf.getvalue()


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
    notes (list of {pitch, start, end, velocity}), and duration_s.

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
        _, midi_data, _note_events = predict(
            in_path,
            onset_threshold=onset_threshold,
            frame_threshold=frame_threshold,
        )
        midi_path = os.path.join(out_dir, "input.mid")
        midi_data.write(midi_path)
        with open(midi_path, "rb") as f:
            midi_bytes = f.read()

    # Post-process MIDI: remove noise, normalize velocities
    try:
        midi_bytes = _clean_midi(midi_bytes)
    except Exception as e:
        logger.warning(f"MIDI cleanup failed, using raw output: {e}")

    # Persist the notes in the final cleaned MIDI so every representation agrees.
    import pretty_midi

    cleaned_midi = pretty_midi.PrettyMIDI(io.BytesIO(midi_bytes))
    notes = [
        {"pitch": note.pitch, "start": note.start, "end": note.end, "velocity": note.velocity}
        for instrument in cleaned_midi.instruments
        for note in instrument.notes
        if not instrument.is_drum
    ]

    wav_bytes = midi_to_wav(midi_bytes)
    return {
        "midi": midi_bytes,
        "wav": wav_bytes,
        "notes": notes,
        "num_notes": len(notes),
    }
