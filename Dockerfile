# AAiOS runtime image (optional deployment path — primary is Windows-native)
#
# Multi-stage build:
#   Stage 1 (builder): install Python deps + build Next.js
#   Stage 2 (runtime): copy built artifacts, slim runtime
#
# Image tags:
#   ghcr.io/rachidsabah/aaios-runtime:latest
#   ghcr.io/rachidsabah/aaios-runtime:<version>
#   ghcr.io/rachidsabah/aaios-runtime:sha-<short-sha>

# syntax=docker/dockerfile:1.7

ARG PYTHON_VERSION=3.12-slim
ARG NODE_VERSION=22-alpine

# ---------------------------------------------------------------------------
# Stage 1a: Python builder
# ---------------------------------------------------------------------------
FROM python:${PYTHON_VERSION} AS python-builder

WORKDIR /build

# Install build deps (kept in builder; not in runtime)
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
COPY core/ ./core/
COPY services/ ./services/
COPY agents/ ./agents/
COPY supervisor/ ./supervisor/
COPY orchestrator/ ./orchestrator/
COPY surfaces/api/ ./surfaces/api/
COPY surfaces/cli/ ./surfaces/cli/

# Build wheel
RUN pip install --no-cache-dir --upgrade pip hatch \
    && hatch build

# ---------------------------------------------------------------------------
# Stage 1b: Web builder
# ---------------------------------------------------------------------------
FROM node:${NODE_VERSION} AS web-builder

WORKDIR /build

COPY package.json pnpm-workspace.yaml .prettierrc.json .prettierignore ./
COPY surfaces/web/package.json ./surfaces/web/package.json
COPY surfaces/web/tsconfig.json ./surfaces/web/tsconfig.json
COPY surfaces/web/next.config.ts ./surfaces/web/next.config.ts
COPY surfaces/web/postcss.config.mjs ./surfaces/web/postcss.config.mjs
COPY surfaces/web/.eslintrc.json ./surfaces/web/.eslintrc.json

RUN corepack enable && corepack prepare pnpm@9 --activate \
    && pnpm install --frozen-lockfile

COPY surfaces/web/src ./surfaces/web/src
COPY surfaces/web/public ./surfaces/web/public

ENV NEXT_PUBLIC_API_BASE=http://127.0.0.1:8000
RUN pnpm --filter '@aaios/web' build

# ---------------------------------------------------------------------------
# Stage 2: Runtime
# ---------------------------------------------------------------------------
FROM python:${PYTHON_VERSION} AS runtime

LABEL org.opencontainers.image.title="AAiOS Runtime"
LABEL org.opencontainers.image.description="Agentic AI Operating System — runtime"
LABEL org.opencontainers.image.source="https://github.com/rachidSabah/aaios"
LABEL org.opencontainers.image.licenses="Apache-2.0"

# Install runtime deps (libpq for asyncpg)
RUN apt-get update && apt-get install -y --no-install-recommends \
        libpq5 \
        tini \
        curl \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --shell /bin/bash aaios

WORKDIR /app

# Install the wheel from the builder
COPY --from=python-builder /build/dist/*.whl /tmp/
RUN pip install --no-cache-dir /tmp/*.whl \
    && rm /tmp/*.whl

# Copy the built Next.js output
COPY --from=web-builder /build/surfaces/web/.next ./surfaces/web/.next
COPY --from=web-builder /build/surfaces/web/public ./surfaces/web/public
COPY --from=web-builder /build/surfaces/web/package.json ./surfaces/web/package.json
COPY --from=web-builder /build/node_modules ./node_modules
COPY --from=web-builder /build/surfaces/web/node_modules ./surfaces/web/node_modules

# Default config
COPY config/defaults.yaml /etc/aaios/config.yaml

# Switch to non-root
USER aaios

EXPOSE 8000 3000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8000/healthz || exit 1

ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["python", "-m", "uvicorn", "surfaces.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
