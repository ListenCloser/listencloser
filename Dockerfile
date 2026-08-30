FROM ubuntu:22.04

ARG USER_ID=501
ARG GROUP_ID=501
ARG OPENCODE_VERSION=1.18.25
ARG SUPABASE_CLI_VERSION=2.113.0

ENV DEBIAN_FRONTEND=noninteractive
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    build-essential \
    git \
    vim-tiny \
    sudo \
    python3.11 \
    python3.11-dev \
    python3-pip \
    python3-venv \
    libsndfile1 \
    ffmpeg \
    fluidsynth \
    && rm -rf /var/lib/apt/lists/*

RUN curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

# Keep the developer/container toolchain reproducible. Supabase matches the
# version used by real-stack CI; OpenCode is pinned to the current stable npm
# release rather than changing underneath an unchanged repository commit.
RUN npm install -g \
    "opencode-ai@${OPENCODE_VERSION}" \
    "supabase@${SUPABASE_CLI_VERSION}"
RUN pip3 install --no-cache-dir uv==0.12.6

RUN npx playwright install --with-deps chromium

RUN update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1

RUN groupadd -g ${GROUP_ID} dev \
    && useradd -m -u ${USER_ID} -g dev -s /bin/bash dev \
    && echo "dev ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers

WORKDIR /workspace

USER dev

ENV PATH="/home/dev/.local/bin:$PATH"

CMD ["/bin/bash"]
