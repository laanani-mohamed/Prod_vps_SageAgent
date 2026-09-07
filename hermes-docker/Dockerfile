# ============================================================================
# Hermes Agent - Dockerfile
# Nous Research - https://hermes-agent.nousresearch.com
# ============================================================================
# Base : Ubuntu 22.04 LTS (jammy) — compatible Playwright & Python 3.11
FROM ubuntu:22.04

# ── Labels ──────────────────────────────────────────────────────────────────
LABEL maintainer="Hermes Agent Docker Setup"
LABEL description="Hermes AI Agent by Nous Research"
LABEL org.opencontainers.image.source="https://github.com/NousResearch/hermes-agent"

# ── Variables d'environnement de base ───────────────────────────────────────
ENV DEBIAN_FRONTEND=noninteractive \
    TZ=UTC \
    HOME=/root \
    HERMES_HOME=/root/.hermes \
    PATH="/root/.local/bin:/usr/local/bin:$PATH" \
    PYTHONPATH="" \
    PYTHONHOME="" \
    UV_NO_CONFIG=1

# ── 1. Paquets système ───────────────────────────────────────────────────────
RUN apt-get update -qq && \
    apt-get install -y --no-install-recommends \
        curl wget git ca-certificates gnupg lsb-release \
        build-essential libssl-dev libffi-dev \
        unzip xz-utils file ripgrep ffmpeg \
        libglib2.0-0 libnss3 libnspr4 libdbus-1-3 \
        libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 \
        libxkbcommon0 libxcomposite1 libxdamage1 libxfixes3 \
        libxrandr2 libgbm1 libasound2 libpango-1.0-0 \
        libcairo2 libatspi2.0-0 libwayland-client0 \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# ── 2. Node.js 22 ───────────────────────────────────────────────────────────
RUN curl -fsSL https://deb.nodesource.com/setup_22.x | bash - && \
    apt-get install -y nodejs && \
    apt-get clean && rm -rf /var/lib/apt/lists/* && \
    node --version && npm --version

# ── 3. Installation de Hermes Agent ─────────────────────────────────────────
RUN curl -fsSL https://hermes-agent.nousresearch.com/install.sh | \
    bash -s -- --skip-setup --skip-browser --non-interactive

# ── 4. Vérification ─────────────────────────────────────────────────────────
RUN which hermes || (echo "ERREUR: hermes introuvable dans PATH" && exit 1)

# ── 5. Volume données persistantes ──────────────────────────────────────────
RUN mkdir -p /root/.hermes /data
VOLUME ["/root/.hermes"]

# ── 6. Ports ────────────────────────────────────────────────────────────────
EXPOSE 3000 8080

# ── 7. Entrypoint ────────────────────────────────────────────────────────────
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

WORKDIR /root
ENTRYPOINT ["/entrypoint.sh"]
CMD ["hermes"]
