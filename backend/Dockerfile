FROM ghcr.io/astral-sh/uv:0.12.6 AS uv

FROM python:3.11-slim AS builder

WORKDIR /app
COPY --from=uv /uv /uvx /bin/
COPY pyproject.toml uv.lock ./

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    TORCH_HOME=/app/.cache/torch

RUN uv sync --locked --no-dev

# TensorFlow 2.15 publishes a tiny Linux ARM64 metapackage whose wheel-specific
# dependency points at the real AWS-maintained runtime. The current uv lock does
# not carry that wheel-specific edge, so an ARM image can otherwise contain the
# 2 KB `tensorflow` shim without an importable TensorFlow implementation. Basic
# Pitch then has no available model runtime and crashes while defining its
# default model path (`_default_model_type`). Install the matching ARM runtime
# explicitly in the image; all of its Python dependencies are already present
# from the locked TensorFlow dependency set above.
RUN if [ "$(uname -m)" = "aarch64" ]; then \
      uv pip install --python /app/.venv/bin/python --no-deps tensorflow-cpu-aws==2.15.0; \
    fi \
    && /app/.venv/bin/python -c "from basic_pitch import ICASSP_2022_MODEL_PATH; from basic_pitch.inference import predict; assert ICASSP_2022_MODEL_PATH"

# Beat This otherwise downloads its ~78 MB final0 checkpoint on the first user
# analysis via torch.hub. Bake the exact model into the image so a fresh worker
# does not depend on external network availability or spend the request budget
# downloading weights. Keep the digest pinned because the upstream URL is not
# content-addressed.
RUN /app/.venv/bin/python -c "from beat_this.inference import load_checkpoint; load_checkpoint('final0')" \
    && sha256sum /app/.cache/torch/hub/checkpoints/beat_this-final0.ckpt \
    && echo "8c328b45f59d8dd3dff219253ff6a8d6482be57d0133a29140e2febbf8eb8331  /app/.cache/torch/hub/checkpoints/beat_this-final0.ckpt" | sha256sum --check -


# MuseScore Studio is a GPL-3.0 external notation application. The shared
# installer owns the exact release/build and per-architecture digests used by
# both the production image and host-based database integration CI. Extract the
# AppImage at build time so runtime conversion does not require FUSE.
FROM python:3.11-slim AS musescore

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates curl \
    && rm -rf /var/lib/apt/lists/*

COPY scripts/install_musescore.sh /usr/local/bin/install-musescore
RUN bash /usr/local/bin/install-musescore /opt/musescore


FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libsndfile1 ffmpeg fluidsynth fluid-soundfont-gm curl \
    libegl1 libopengl0 libnss3 libgpg-error0 libxcb-cursor0 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/.cache /app/.cache
COPY --from=musescore /opt/musescore /opt/musescore
ENV PATH="/app/.venv/bin:$PATH" \
    TORCH_HOME=/app/.cache/torch \
    MUSESCORE_BIN=/opt/musescore/AppRun

# Fail the image build if the pinned external notation runtime cannot execute in
# the final production-shaped layer. Exercise the same JSON batch interface the
# adapter uses and require both of its derived artifacts: MusicXML + notation
# MIDI. Pass Qt's platform explicitly because MuseScore's AppRun can select xcb
# even when QT_QPA_PLATFORM is set in a headless container. MuseScore Studio
# 4.7.4's AppImage accepts --job here but does not accept the older
# --no-synthesizer/--no-midi/--no-webview long options.
# The existing native amd64/arm64 image matrix therefore verifies both assets.
RUN set -eux; \
    QT_QPA_PLATFORM=offscreen SKIP_LIBJACK=1 "$MUSESCORE_BIN" -platform offscreen --version; \
    python -c "import json, pretty_midi; m=pretty_midi.PrettyMIDI(); i=pretty_midi.Instrument(program=0); i.notes.append(pretty_midi.Note(velocity=90,pitch=60,start=0.0,end=1.0)); m.instruments.append(i); m.write('/tmp/musescore-smoke.mid'); open('/tmp/musescore-smoke-job.json','w',encoding='utf-8').write(json.dumps([{'in':'/tmp/musescore-smoke.mid','out':['/tmp/musescore-smoke.musicxml','/tmp/musescore-smoke-out.mid']}]))"; \
    QT_QPA_PLATFORM=offscreen SKIP_LIBJACK=1 "$MUSESCORE_BIN" -platform offscreen \
      --job /tmp/musescore-smoke-job.json; \
    grep -aq '<score-partwise' /tmp/musescore-smoke.musicxml; \
    python -c "assert open('/tmp/musescore-smoke-out.mid','rb').read(4) == b'MThd'"; \
    rm -f /tmp/musescore-smoke.mid /tmp/musescore-smoke.musicxml \
      /tmp/musescore-smoke-out.mid /tmp/musescore-smoke-job.json

COPY . .

RUN addgroup --system --gid 1001 appuser \
    && adduser --disabled-password --gecos "" --uid 1001 --gid 1001 appuser \
    && chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
