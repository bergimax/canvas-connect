# syntax=docker/dockerfile:1

# ---- 1. build the frontend (TanStack Start / nitro, node-server target) ----
FROM node:20-slim AS frontend-build
WORKDIR /app/frontend

COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ ./
# The frontend's vite config defaults nitro to a Cloudflare Workers build;
# node-server produces a plain Node HTTP server + static assets instead,
# which is what the backend proxies to at runtime (see docker-entrypoint.sh).
ENV NITRO_PRESET=node-server
RUN npm run build
# -> /app/frontend/.output/public (static assets)
# -> /app/frontend/.output/server (self-contained Node server)

# ---- 2. backend image: FastAPI + the built frontend ----
FROM python:3.12-slim AS backend

# Node is needed only to run the already-built frontend server bundle above,
# not to build anything — kept as a separate, pinned install from the same
# major version used to build it.
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates gnupg \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && apt-get purge -y --auto-remove curl gnupg \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

WORKDIR /app/backend

# Install dependencies first so this layer is cached independently of app code.
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY backend/app ./app
RUN uv sync --frozen --no-dev

COPY backend/docker-entrypoint.sh ./docker-entrypoint.sh
RUN chmod +x ./docker-entrypoint.sh

COPY --from=frontend-build /app/frontend/.output/public /app/frontend/public
COPY --from=frontend-build /app/frontend/.output/server /app/frontend/server

ENV PATH="/app/backend/.venv/bin:${PATH}" \
    FRONTEND_SERVER_ENTRY=/app/frontend/server/index.mjs \
    PORT=8000

EXPOSE 8000

ENTRYPOINT ["./docker-entrypoint.sh"]
