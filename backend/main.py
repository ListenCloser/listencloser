import base64
import contextvars
import json
import logging
import os
import re
import tempfile
import threading
import time
import uuid
from datetime import UTC, datetime

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from analyze import analyze_midi
from music_features import _sanitize_fmt, convert_format, enhance_audio, transcribe_audio

_request_id_ctx = contextvars.ContextVar("request_id", default="none")


class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
            "req_id": getattr(record, "req_id", "none"),
        }
        for key in (
            "method",
            "path",
            "status",
            "duration_ms",
            "input_bytes",
            "output_bytes",
            "step",
            "step_ms",
            "num_notes",
            "fmt",
        ):
            val = getattr(record, key, None)
            if val is not None:
                payload[key] = val
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


_json_handler = logging.StreamHandler()
_json_handler.setFormatter(_JsonFormatter())
logging.basicConfig(level=logging.INFO, handlers=[_json_handler], force=True)
logger = logging.getLogger("backend")

try:
    import sentry_sdk  # noqa: I001
    from sentry_sdk.integrations.starlette import StarletteIntegration  # noqa: I001
    from sentry_sdk.integrations.fastapi import FastAPIIntegration  # noqa: I001

    _sentry_dsn = os.environ.get("SENTRY_DSN_BACKEND") or os.environ.get("SENTRY_DSN")
    if _sentry_dsn:
        sentry_sdk.init(
            dsn=_sentry_dsn,
            environment=os.environ.get("SENTRY_ENV", "production"),
            integrations=[StarletteIntegration(), FastAPIIntegration()],
            traces_sample_rate=float(os.environ.get("SENTRY_TRACES_SAMPLE_RATE", "0.1")),
            send_default_pii=False,
            release=os.environ.get("RELEASE", "backend@0.2.0"),
        )
        logger.info("sentry_initialized")
except ImportError:
    logger.warning("sentry_sdk_not_installed")

limiter = Limiter(key_func=get_remote_address, default_limits=["60/minute"])

security = HTTPBearer(auto_error=False)

MAX_UPLOAD_BYTES = int(os.environ.get("MAX_UPLOAD_BYTES", "26214400"))  # 25 MB
_MIDI_KEY_RE = re.compile(r"^midi/[\w.\-]+/[\w.\-]+$")


def _now() -> str:
    return datetime.now(UTC).isoformat()


_ANALYZE_EXTS = {
    "wav": "wav",
    "wave": "wav",
    "mp3": "mp3",
    "flac": "flac",
    "ogg": "ogg",
    "m4a": "m4a",
    "aac": "aac",
}


def _analyze_ext(fmt: str) -> str:
    return _ANALYZE_EXTS.get(fmt.lower(), "wav")


def _split_storage_path(path: str) -> tuple[str, str]:
    """Split 'library/...' or 'midi/...' into (bucket, key).

    The frontend uploads library files with keys like
    ``library/<uid>/<ts>-<name>.m4a`` inside the ``library`` bucket, so the
    full path (including the ``library/`` prefix) is the actual storage key.

    Raises HTTPException if the path doesn't match a known prefix or key is empty.
    """
    if path.startswith("library/"):
        if ".." in path or path == "library/":
            raise HTTPException(status_code=400, detail="invalid library path")
        return "library", path
    if path.startswith("midi/"):
        key = path[len("midi/") :]
        if not key or ".." in key:
            raise HTTPException(status_code=400, detail="invalid midi key")
        return "midi", key
    raise HTTPException(status_code=400, detail="path must start with library/ or midi/")


_sb_client = None
_sb_lock = threading.Lock()


def _sb():
    global _sb_client
    if _sb_client is not None:
        return _sb_client
    with _sb_lock:
        if _sb_client is not None:
            return _sb_client
        from supabase import create_client

        url = os.environ.get("SUPABASE_URL")
        key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
        if not url or not key:
            return None
        _sb_client = create_client(url, key)
        return _sb_client


def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    sb = _sb()
    if not sb:
        raise HTTPException(status_code=500, detail="Auth not configured")
    try:
        user = sb.auth.get_user(token)
        return user
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
        ) from None


def verify_token_optional(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
):
    """Like verify_token but allows anonymous access. Returns the user when a
    valid bearer token is supplied, otherwise None. Used by read-only/public
    endpoints (e.g. /music/analyze) so unauthenticated users can still use them."""
    if not credentials:
        return None
    sb = _sb()
    if not sb:
        return None
    try:
        return sb.auth.get_user(credentials.credentials)
    except Exception:
        return None


app = FastAPI(title="hello-ai backend", version="0.3.0")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

try:
    from fastapi.middleware.cors import CORSMiddleware

    _cors_origins = [
        "https://hello-ai-wheat.vercel.app",
        "http://localhost:3000",
    ]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )
except ImportError:
    pass


@app.middleware("http")
async def observability_middleware(request: Request, call_next):
    req_id = request.headers.get("x-request-id") or uuid.uuid4().hex[:16]
    token = _request_id_ctx.set(req_id)
    start = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        logger.exception("request_failed", extra={"req_id": req_id})
        raise
    finally:
        _request_id_ctx.reset(token)
    duration_ms = round((time.perf_counter() - start) * 1000, 2)
    response.headers["x-request-id"] = req_id
    logger.info(
        "request_handled",
        extra={
            "req_id": req_id,
            "method": request.method,
            "path": request.url.path,
            "status": response.status_code,
            "duration_ms": duration_ms,
        },
    )
    return response


def _sb_upload(bucket: str, path: str, data: bytes, content_type: str) -> str:
    """Upload bytes to a Supabase bucket (service role) and return public URL."""
    sb = _sb()
    if not sb:
        raise HTTPException(status_code=500, detail="Supabase not configured on server")
    sb.storage.from_(bucket).upload(path, data, {"content-type": content_type})
    public = sb.storage.from_(bucket).get_public_url(path)
    return public if isinstance(public, str) else public.get("publicUrl", "")


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------
@app.get("/health")
def health(request: Request):
    return {"status": "ok"}


@app.get("/health/live")
def health_live(request: Request):
    return {"status": "alive"}


@app.get("/health/ready")
def health_ready(request: Request):
    sb = _sb()
    st = "ready" if sb else "degraded"
    return {"status": st, "supabase": sb is not None}


# ---------------------------------------------------------------------------
# Music features: library + transcription
# ---------------------------------------------------------------------------
class TranscribeRequest(BaseModel):
    audio_base64: str | None = None
    library_path: str | None = None
    fmt: str = "wav"
    onset_threshold: float = 0.5
    frame_threshold: float = 0.3
    upload: bool = True


def _load_audio_from_request(
    audio_base64: str | None,
    library_path: str | None,
) -> bytes:
    """Decode base64 audio or download from the library bucket."""
    if audio_base64:
        try:
            audio = base64.b64decode(audio_base64)
        except Exception as e:
            raise HTTPException(status_code=400, detail="invalid base64") from e
        if len(audio) > MAX_UPLOAD_BYTES:
            raise HTTPException(
                status_code=413,
                detail=f"payload too large (max {MAX_UPLOAD_BYTES} bytes)",
            )
        return audio
    if library_path:
        sb = _sb()
        if not sb:
            raise HTTPException(status_code=500, detail="Supabase not configured")
        bucket, key = _split_storage_path(library_path)
        try:
            data = sb.storage.from_(bucket).download(key)
        except Exception as e:
            err_msg = str(e)
            err_lower = err_msg.lower()
            if "404" in err_msg or "not_found" in err_lower or "Object not found" in err_msg:
                raise HTTPException(status_code=404, detail="file not found in library") from e
            raise HTTPException(status_code=500, detail="storage error") from e
        return data if isinstance(data, bytes | bytearray) else data.read()
    raise HTTPException(status_code=400, detail="audio_base64 or library_path required")


class UploadLibraryRequest(BaseModel):
    name: str = ""
    data_base64: str
    fmt: str = "wav"


@app.post("/music/library")
@limiter.limit("10/minute")
async def upload_library(req: UploadLibraryRequest, request: Request, _auth=Depends(verify_token)):
    """Store a raw audio file in the `library` bucket.

    Body: { name, data_base64, fmt }. Returns { path, url }.
    """
    name = (req.name or f"{uuid.uuid4().hex}").replace("/", "_")
    fmt = _sanitize_fmt(req.fmt)
    try:
        raw = base64.b64decode(req.data_base64)
    except Exception as e:
        raise HTTPException(status_code=400, detail="invalid base64") from e
    if len(raw) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"payload too large (max {MAX_UPLOAD_BYTES} bytes)",
        )
    ext = fmt.lstrip(".")
    path = f"library/{uuid.uuid4().hex}-{name}.{ext}"
    url = _sb_upload("library", path, raw, f"audio/{ext}")
    return {"path": path, "url": url}


class EnhanceRequest(BaseModel):
    audio_base64: str | None = None
    library_path: str | None = None
    fmt: str = "wav"
    upload: bool = True


@app.post("/music/enhance")
@limiter.limit("20/minute")
def enhance(req: EnhanceRequest, request: Request, _auth=Depends(verify_token_optional)):
    """Cleanup a raw recording (denoise/declip/normalize) via ffmpeg."""
    audio = _load_audio_from_request(req.audio_base64, req.library_path)
    t0 = time.perf_counter()
    logger.info("enhance_start", extra={"input_bytes": len(audio)})

    try:
        cleaned = enhance_audio(audio, fmt=req.fmt)
    except Exception as e:
        logger.exception("enhance_failed")
        raise HTTPException(status_code=500, detail="enhance failed") from e

    elapsed_ms = round((time.perf_counter() - t0) * 1000)
    logger.info(
        "enhance_done",
        extra={
            "step": "ffmpeg",
            "step_ms": elapsed_ms,
            "output_bytes": len(cleaned),
        },
    )

    out = {"wav_base64": base64.b64encode(cleaned).decode("ascii")}
    if req.upload:
        path = f"library/{uuid.uuid4().hex}-enhanced.wav"
        out["url"] = _sb_upload("library", path, cleaned, "audio/wav")
    return out


@app.post("/music/transcribe")
@limiter.limit("10/minute")
def transcribe(req: TranscribeRequest, request: Request, _auth=Depends(verify_token_optional)):
    """Transcribe audio -> MIDI (+ synthesized WAV + note events)."""
    audio = _load_audio_from_request(req.audio_base64, req.library_path)
    t0 = time.perf_counter()
    logger.info("transcribe_start", extra={"input_bytes": len(audio), "fmt": req.fmt})

    try:
        result = transcribe_audio(
            audio,
            fmt=req.fmt,
            onset_threshold=req.onset_threshold,
            frame_threshold=req.frame_threshold,
        )
    except Exception as e:
        logger.exception("transcription_failed")
        raise HTTPException(status_code=500, detail="transcription failed") from e

    t1 = time.perf_counter()
    logger.info(
        "transcribe_done",
        extra={
            "step": "basic_pitch",
            "step_ms": round((t1 - t0) * 1000),
            "num_notes": result["num_notes"],
        },
    )

    midi = result["midi"]
    wav = result["wav"]
    out = {
        "notes": result["notes"],
        "num_notes": result["num_notes"],
        "midi_base64": base64.b64encode(midi).decode("ascii"),
        "wav_base64": base64.b64encode(wav).decode("ascii"),
    }
    if req.upload:
        t2 = time.perf_counter()
        midi_path = f"midi/backend/{uuid.uuid4().hex}.mid"
        wav_path = f"midi/backend/{uuid.uuid4().hex}.wav"
        out["midi_url"] = _sb_upload("midi", midi_path, midi, "audio/midi")
        out["wav_url"] = _sb_upload("midi", wav_path, wav, "audio/wav")
        upload_ms = round((time.perf_counter() - t2) * 1000)
        logger.info(
            "transcribe_upload",
            extra={
                "step": "supabase_upload",
                "step_ms": upload_ms,
            },
        )
    total_ms = round((time.perf_counter() - t0) * 1000)
    logger.info("transcribe_total", extra={"step": "total", "step_ms": total_ms})
    return out


class SynthRequest(BaseModel):
    midi_base64: str


@app.post("/music/synth")
@limiter.limit("30/minute")
def synth(req: SynthRequest, request: Request, _auth=Depends(verify_token_optional)):
    """Convert MIDI to WAV audio using FluidSynth (or numpy fallback)."""
    try:
        midi_bytes = base64.b64decode(req.midi_base64, validate=True)
    except Exception:
        raise HTTPException(status_code=400, detail="invalid midi base64") from None
    if len(midi_bytes) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"payload too large (max {MAX_UPLOAD_BYTES} bytes)",
        )

    from music_features import midi_to_wav

    t0 = time.perf_counter()
    try:
        wav = midi_to_wav(midi_bytes)
    except Exception as e:
        logger.exception("synth_failed")
        raise HTTPException(status_code=500, detail="MIDI synthesis failed") from e
    elapsed = round((time.perf_counter() - t0) * 1000)
    logger.info("synth_done", extra={"step": "midi_to_wav", "step_ms": elapsed})

    return {
        "wav_base64": base64.b64encode(wav).decode("ascii"),
    }


class AnalyzeRequest(BaseModel):
    midi_base64: str


@app.post("/music/analyze")
@limiter.limit("30/minute")
def analyze(req: AnalyzeRequest, request: Request, _auth=Depends(verify_token_optional)):
    """Analyze MIDI for key, tempo, time signature, chords, Roman numerals, etc."""
    try:
        midi_bytes = base64.b64decode(req.midi_base64, validate=True)
    except Exception:
        raise HTTPException(status_code=400, detail="invalid midi base64") from None
    if len(midi_bytes) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"payload too large (max {MAX_UPLOAD_BYTES} bytes)",
        )

    t0 = time.perf_counter()
    logger.info("analyze_start", extra={"input_bytes": len(midi_bytes)})

    with tempfile.TemporaryDirectory() as td:
        midi_path = os.path.join(td, "input.mid")
        with open(midi_path, "wb") as f:
            f.write(midi_bytes)

        try:
            result = analyze_midi(midi_path)
        except Exception:
            logger.exception("analysis_failed")
            raise HTTPException(status_code=500, detail="analysis failed") from None

    elapsed_ms = round((time.perf_counter() - t0) * 1000)
    logger.info(
        "analyze_done",
        extra={
            "step": "analyze_midi",
            "step_ms": elapsed_ms,
        },
    )
    return result


class ConvertRequest(BaseModel):
    source: str
    data_base64: str
    target: str = "auto"


@app.post("/music/convert")
@limiter.limit("30/minute")
def convert(req: ConvertRequest, request: Request, _auth=Depends(verify_token_optional)):
    """Convert between MIDI and MusicXML formats."""
    try:
        data = base64.b64decode(req.data_base64, validate=True)
    except Exception:
        raise HTTPException(status_code=400, detail="invalid base64") from None
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"payload too large (max {MAX_UPLOAD_BYTES} bytes)",
        )

    source = req.source.lower()
    if source not in ("midi", "musicxml"):
        raise HTTPException(status_code=400, detail="source must be 'midi' or 'musicxml'")

    target = req.target.lower()
    if target == "auto":
        target = "musicxml" if source == "midi" else "midi"

    try:
        result_bytes = convert_format(data, source, target)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception:
        logger.exception("conversion failed")
        raise HTTPException(status_code=500, detail="conversion failed") from None

    return {
        "data_base64": base64.b64encode(result_bytes).decode("ascii"),
        "format": target,
    }


@app.delete("/music/library/transcription/{record_id:path}")
@limiter.limit("30/minute")
def delete_transcription(record_id: str, request: Request, auth=Depends(verify_token)):
    """Delete a saved transcription from the `transcriptions` bucket."""
    segments = record_id.split("/")
    if len(segments) < 2 or segments[0] != "transcriptions":
        raise HTTPException(status_code=400, detail="invalid path")
    user_id = segments[1]
    authed_user_id = getattr(auth.user, "id", None)
    if user_id != authed_user_id:
        raise HTTPException(status_code=403, detail="Forbidden")
    sb = _sb()
    if not sb:
        raise HTTPException(status_code=500, detail="Supabase not configured")
    key = record_id.replace("transcriptions/", "", 1)
    sb.storage.from_("transcriptions").remove([key])
    return {"status": "deleted"}


@app.delete("/music/library/{path:path}")
@limiter.limit("30/minute")
def delete_library_file(path: str, request: Request, auth=Depends(verify_token)):
    """Delete a file from the `library` bucket using the service role key."""
    segments = path.split("/")
    if len(segments) < 2 or segments[0] != "library":
        raise HTTPException(status_code=400, detail="invalid path")
    user_id = segments[1]
    authed_user_id = getattr(auth.user, "id", None)
    if user_id != authed_user_id:
        raise HTTPException(status_code=403, detail="Forbidden")
    sb = _sb()
    if not sb:
        raise HTTPException(status_code=500, detail="Supabase not configured")
    sb.storage.from_("library").remove([path])
    return {"status": "deleted"}
