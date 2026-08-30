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

# The production image hosts both the API and durable music worker today, so it
# explicitly requests the heavy ML/model runtime while ordinary dev/CI can stay
# on the lightweight base dependency set.
RUN uv sync --locked --no-dev --group worker

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


FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libsndfile1 ffmpeg fluidsynth fluid-soundfont-gm curl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/.cache /app/.cache
ENV PATH="/app/.venv/bin:$PATH" \
    TORCH_HOME=/app/.cache/torch

COPY . .

RUN addgroup --system --gid 1001 appuser \
    && adduser --disabled-password --gecos "" --uid 1001 --gid 1001 appuser \
    && chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
