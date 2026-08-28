FROM ubuntu:22.04

ARG USER_ID=501
ARG GROUP_ID=501

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

RUN npm install -g opencode-ai supabase
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
