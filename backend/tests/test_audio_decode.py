import io
import wave

import pytest

import audio_processing
import music_features


def _tiny_wav() -> bytes:
    output = io.BytesIO()
    with wave.open(output, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(8000)
        wav.writeframes(b"\x00\x00" * 800)
    return output.getvalue()


def test_music_features_reexports_audio_processing_helpers():
    assert music_features.decode_audio_to_wav is audio_processing.decode_audio_to_wav
    assert music_features.enhance_audio is audio_processing.enhance_audio


def test_decode_audio_to_wav_returns_valid_pcm():
    decoded = music_features.decode_audio_to_wav(_tiny_wav(), fmt="wav")
    assert decoded.startswith(b"RIFF")
    assert b"WAVE" in decoded[:16]


def test_decode_audio_to_wav_rejects_invalid_container():
    with pytest.raises(ValueError, match="Audio decoding failed"):
        music_features.decode_audio_to_wav(b"not an audio file", fmt="m4a")
