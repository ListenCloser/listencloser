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


# PM2S is an MIT-licensed learned performance-MIDI -> score-MIDI codebase. It
# is not packaged on PyPI, so bake an exact source commit plus the public model
# artifacts from the immutable Zenodo record into the experimental worker image.
# The code license and model-record provenance are tracked separately; verify
# checkpoint terms again before any future commercial deployment. Do not install
# PM2S's historical 2022 dependency pins: the adapter exercises it against the
# maintained worker Torch/NumPy/pretty-midi/mido stack. Upstream pm2s.py has an
# unused pandas import; remove only that import rather than adding an unrelated
# runtime dependency.
FROM python:3.11-slim AS pm2s

ARG PM2S_COMMIT=9586f91cd16aaa50dbb82f720f6a34a3e0186f47
ARG PM2S_MODEL_RECORD=10520196

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates curl \
    && rm -rf /var/lib/apt/lists/*

RUN set -eux; \
    mkdir -p /opt/pm2s /opt/pm2s-models; \
    curl --fail --location --retry 3 \
      "https://github.com/cheriell/PM2S/archive/${PM2S_COMMIT}.tar.gz" \
      -o /tmp/pm2s.tar.gz; \
    tar -xzf /tmp/pm2s.tar.gz --strip-components=1 -C /opt/pm2s; \
    rm /tmp/pm2s.tar.gz; \
    sed -i '/^import pandas as pd$/d' /opt/pm2s/pm2s/pm2s.py; \
    for model in \
      RNNJointBeatModel.pth \
      RNNHandPartModel.pth \
      RNNKeySignatureModel.pth \
      CNNTimeSignatureModel.pth; do \
        curl --fail --location --retry 3 \
          "https://zenodo.org/records/${PM2S_MODEL_RECORD}/files/${model}?download=1" \
          -o "/opt/pm2s-models/${model}"; \
        test -s "/opt/pm2s-models/${model}"; \
    done; \
    printf '%s\n' \
      "PM2S source commit ${PM2S_COMMIT}" \
      "Code license: MIT" \
      "Source: https://github.com/cheriell/PM2S/tree/${PM2S_COMMIT}" \
      "Model record: https://zenodo.org/records/${PM2S_MODEL_RECORD}" \
      > /opt/pm2s/LISTENCLOSER_PROVENANCE.txt


# MuseScore Studio is a GPL-3.0 external notation application. Use the last
# clearly published stable release, pin the official GitHub-release digest for
# each supported worker architecture, and extract the AppImage at build time so
# runtime conversion does not require FUSE. The exact corresponding source is
# available from the same v4.7.4 upstream release.
FROM python:3.11-slim AS musescore

ARG MUSESCORE_VERSION=4.7.4
ARG MUSESCORE_BUILD=260706075

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates curl \
    && rm -rf /var/lib/apt/lists/*

RUN set -eux; \
    deb_arch="$(dpkg --print-architecture)"; \
    case "$deb_arch" in \
      amd64) \
        asset_arch="x86_64"; \
        expected_sha="9233ed1b87d3e6b45722278f3c286dcd41e83da778bd0f80a1dd04949696ad93" \
        ;; \
      arm64) \
        asset_arch="aarch64"; \
        expected_sha="162ae55b317660f196b2e73d566bdb45c1e990ed4cc140709d25d97b9ef366b0" \
        ;; \
      *) \
        echo "Unsupported MuseScore architecture: $deb_arch" >&2; \
        exit 1 \
        ;; \
    esac; \
    asset="MuseScore-Studio-${MUSESCORE_VERSION}.${MUSESCORE_BUILD}-${asset_arch}.AppImage"; \
    url="https://github.com/musescore/MuseScore/releases/download/v${MUSESCORE_VERSION}/${asset}"; \
    curl --fail --location --retry 3 --output /tmp/musescore.AppImage "$url"; \
    echo "${expected_sha}  /tmp/musescore.AppImage" | sha256sum --check -; \
    chmod +x /tmp/musescore.AppImage; \
    cd /opt; \
    /tmp/musescore.AppImage --appimage-extract >/dev/null; \
    mv squashfs-root musescore; \
    rm /tmp/musescore.AppImage; \
    printf '%s\n' \
      "MuseScore Studio ${MUSESCORE_VERSION}.${MUSESCORE_BUILD}" \
      "License: GPL-3.0" \
      "Source: https://github.com/musescore/MuseScore/releases/tag/v${MUSESCORE_VERSION}" \
      > /opt/musescore/LISTENCLOSER_PROVENANCE.txt


FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libsndfile1 ffmpeg fluidsynth fluid-soundfont-gm curl \
    libegl1 libopengl0 libnss3 libgpg-error0 libxcb-cursor0 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/.cache /app/.cache
COPY --from=pm2s /opt/pm2s /opt/pm2s
COPY --from=pm2s /opt/pm2s-models /opt/pm2s-models
COPY --from=musescore /opt/musescore /opt/musescore
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONPATH="/opt/pm2s" \
    PM2S_MODEL_DIR=/opt/pm2s-models \
    TORCH_HOME=/app/.cache/torch \
    MUSESCORE_BIN=/opt/musescore/AppRun

# Fail image construction if the pinned PM2S source cannot import against the
# maintained production Python stack or if any required baked model disappeared.
# Model loading/inference is exercised by the production-shaped score test rather
# than silently allowing first-request network downloads.
RUN set -eux; \
    python -c "from pm2s.pm2s import CRNNJointPM2S; assert CRNNJointPM2S"; \
    for model in \
      RNNJointBeatModel.pth \
      RNNHandPartModel.pth \
      RNNKeySignatureModel.pth \
      CNNTimeSignatureModel.pth; do \
        test -s "/opt/pm2s-models/${model}"; \
    done

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
