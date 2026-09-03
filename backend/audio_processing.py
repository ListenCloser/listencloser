"""FFmpeg-backed audio decoding and preprocessing helpers.

This module owns container sanitization and audio-only subprocess work. The
legacy ``music_features`` module re-exports the public helpers while callers
migrate toward narrower module boundaries. Callers intentionally remain on the
compatibility surface during this extraction.
"""

from __future__ import annotations

import logging
import os
import subprocess
import tempfile
import wave

logger = logging.getLogger("music_features")

_FFMPEG_TIMEOUT = 120
_ALLOWED_AUDIO_FORMATS = frozenset({".wav", ".flac", ".ogg", ".mp3", ".m4a", ".aac", ".webm"})
_DEFAULT_MAX_DECODED_AUDIO_SECONDS = 600.0
_DECODE_OVERFLOW_PROBE_SECONDS = 1.0


def _sanitize_fmt(fmt: str) -> str:
    ext = fmt if fmt.startswith(".") else f".{fmt}"
    return ext if ext in _ALLOWED_AUDIO_FORMATS else ".wav"


def _max_decoded_audio_seconds() -> float:
    raw = os.environ.get(
        "MAX_DECODED_AUDIO_SECONDS",
        str(_DEFAULT_MAX_DECODED_AUDIO_SECONDS),
    )
    try:
        return max(1.0, float(raw))
    except ValueError:
        return _DEFAULT_MAX_DECODED_AUDIO_SECONDS


def _wav_duration_seconds(path: str) -> float:
    with wave.open(path, "rb") as wav_file:
        frame_rate = wav_file.getframerate()
        if frame_rate <= 0:
            raise ValueError("Decoded audio has an invalid sample rate")
        return wav_file.getnframes() / frame_rate


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
    """Decode a supported upload into a validated, duration-bounded mono PCM WAV."""
    suffix = _sanitize_fmt(fmt)
    max_duration_seconds = _max_decoded_audio_seconds()
    decode_ceiling_seconds = max_duration_seconds + _DECODE_OVERFLOW_PROBE_SECONDS
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
                    "-t",
                    str(decode_ceiling_seconds),
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
        try:
            decoded_duration_seconds = _wav_duration_seconds(output_path)
        except (OSError, wave.Error) as error:
            raise ValueError("Audio decoding produced an invalid WAV") from error
        if decoded_duration_seconds > max_duration_seconds:
            raise ValueError(f"Audio exceeds maximum duration of {max_duration_seconds:g} seconds")
        with open(output_path, "rb") as file_handle:
            decoded = file_handle.read()
        if not decoded.startswith(b"RIFF") or len(decoded) < 44:
            raise ValueError("Audio decoding produced an invalid WAV")
        return decoded
