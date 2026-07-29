"""Contract test: every route the Next.js app proxies to MUST exist in FastAPI.

The frontend never calls the Oracle backend directly; it goes through
`app/api/*/route.ts` -> `proxyToBackend(path)`. If a proxy target drifts from a
real backend route (typo, renamed endpoint, removed route), the UI silently 500s
in production. This test fails CI on that drift.
"""

import io
import re
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

import main
from music_features import transcribe_audio

REPO_ROOT = Path(__file__).resolve().parents[2]
API_DIR = REPO_ROOT / "app" / "api"

PROXY_RE = re.compile(r'proxyToBackend\(\s*req\s*,\s*["\`]([^"\`]+)["\`]')


def _proxied_paths() -> set[str]:
    paths: set[str] = set()
    if not API_DIR.exists():
        return paths
    for route in API_DIR.rglob("route.ts"):
        text = route.read_text()
        for m in PROXY_RE.finditer(text):
            raw = m.group(1)
            # Expand `{param}` / `${param}` template segments to a placeholder.
            normalized = re.sub(r"\$\{[^}]+\}|\{[^}]+\}", "x", raw)
            paths.add(normalized)
    return paths


def _backend_paths() -> set[tuple[str, frozenset]]:
    result: set[tuple[str, frozenset]] = set()
    for r in main.app.routes:
        methods = getattr(r, "methods", None)
        if not methods:
            continue
        if not (methods & {"GET", "POST", "DELETE", "PUT", "PATCH"}):
            continue
        result.add((r.path, frozenset(methods)))
    return result


PROXIED = _proxied_paths()
BACKEND = _backend_paths()


def _backend_has(path: str, method: str) -> bool:
    # Match ignoring FastAPI path param syntax ({job_id} vs x).
    norm = re.sub(r"\{[^}]+\}", "x", path)
    for bpath, methods in BACKEND:
        bnorm = re.sub(r"\{[^}]+\}", "x", bpath)
        if bnorm == norm and method in methods:
            return True
    return False


@pytest.mark.parametrize("path", sorted(PROXIED))
def test_proxied_route_exists_in_backend(path):
    # Determine the HTTP method the frontend uses for this path.
    method = "POST"  # default
    if (
        path.startswith("/health")
        or path.startswith("/api/v1/jobs/")
        or path.startswith("/api/v1/versions/")
    ):
        method = "GET"
    if path.startswith("/music/library/"):
        method = "DELETE"
    assert PROXIED, "no proxied paths discovered — check app/api scanning"
    assert _backend_has(path, method), (
        f"Frontend proxies to '{path}' ({method}) but no matching backend route exists"
    )


NOTE_KEYS = {"pitch", "start", "end", "velocity"}
FIXTURE_WAV = Path(__file__).resolve().parent / "fixtures" / "sine_a4_c5.wav"


def _sine_wav_bytes() -> bytes:
    """A short synthetic clip: A4 (440Hz) for 0.5s then C5 (523.25Hz) for 0.5s."""
    sr = 22050
    t = np.linspace(0, 1.0, sr, endpoint=False)
    sig = np.zeros(sr, dtype=np.float32)
    seg = sr // 2
    sig[:seg] += 0.3 * np.sin(2 * np.pi * 440.0 * t[:seg])
    sig[seg:] += 0.3 * np.sin(2 * np.pi * 523.25 * t[seg:])
    buf = io.BytesIO()
    sf.write(buf, np.clip(sig, -1.0, 1.0), sr, format="WAV", subtype="PCM_16")
    return buf.getvalue()


def _fixture_wav() -> bytes:
    if FIXTURE_WAV.exists():
        return FIXTURE_WAV.read_bytes()
    FIXTURE_WAV.parent.mkdir(parents=True, exist_ok=True)
    audio = _sine_wav_bytes()
    FIXTURE_WAV.write_bytes(audio)
    return audio


def test_transcribe_contract():
    """`transcribe_audio` MUST return the documented shape: notes (list) where
    each note has pitch/start/end/velocity, num_notes == len(notes), and
    non-empty midi + wav bytes."""
    try:
        import basic_pitch  # noqa: F401
        import pretty_midi  # noqa: F401
    except Exception as e:  # pragma: no cover - environment guard
        pytest.skip(f"transcription deps unavailable: {e}")

    result = transcribe_audio(_fixture_wav(), fmt="wav")

    assert isinstance(result, dict)
    assert "notes" in result and "num_notes" in result
    assert "midi" in result and "wav" in result

    notes = result["notes"]
    assert isinstance(notes, list)
    assert result["num_notes"] == len(notes)

    for note in notes:
        assert isinstance(note, dict)
        assert set(note.keys()) == NOTE_KEYS
        assert isinstance(note["pitch"], int)
        assert isinstance(note["start"], int | float)
        assert isinstance(note["end"], int | float)
        assert isinstance(note["velocity"], int)
        assert note["end"] >= note["start"]

    midi = result["midi"]
    wav = result["wav"]
    assert isinstance(midi, bytes | bytearray) and len(midi) > 0
    assert isinstance(wav, bytes | bytearray) and len(wav) > 0
