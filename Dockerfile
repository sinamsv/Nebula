# syntax=docker/dockerfile:1

# Railway / PaaS Deployment Changes (v1.6.1):
# - EXPOSE 8080 only (no longer also 8000): FastAPI is internal-only since
#   v1.6.1 (bound to 127.0.0.1 in main.py, proxied by Next.js's rewrites())
#   -- it was never meant to be reached directly from outside the
#   container, so publishing/exposing that port was misleading. Next.js
#   (port 8080 by default, or Railway's injected PORT) is the only thing
#   that needs to be reachable from outside.
# - Frontend build stays 100% in the builder stage below (unchanged) --
#   main.py no longer re-checks/rebuilds at container startup (see
#   main.py's module docstring), so what this Dockerfile produces at
#   build time is exactly what ships and runs, with no runtime surprises.
# - Added a HEALTHCHECK hitting Next.js's own root path -- useful for
#   Railway's healthcheck feature and for `docker compose` alike, confirms
#   the single public port is actually accepting connections.
# - How to revert: add back `EXPOSE 8000`, drop the HEALTHCHECK.

# ---- Python build stage: compile wheels so the final image doesn't need gcc/build tools ----
FROM python:3.11-slim AS py-builder

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc \
        libffi-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

# ---- Frontend build stage: install deps + `npm run build` the Next.js app ----
# Separate image (node, not python:3.11-slim) since this stage needs
# Node/npm, not Python -- only its OUTPUT (node_modules + the compiled
# .next/ build) gets copied into the final runtime stage below, so
# none of Node's own build tooling ends up in the image Nebula
# actually ships/runs. This is the ONLY place npm install/build ever
# runs now -- main.py deliberately does NOT re-check or rebuild at
# container startup (see main.py's module docstring for why that broke
# PaaS deployments).
FROM node:20-slim AS frontend-builder

WORKDIR /build/web_frontend

# Copy only the manifest files first so Docker's layer cache can skip
# `npm install` entirely on rebuilds where only application code
# changed, not dependencies -- same reasoning as copying
# requirements.txt before the rest of the backend source above.
COPY web_frontend/package.json web_frontend/package-lock.json* ./
RUN npm install

COPY web_frontend/ ./
# NEXT_PUBLIC_* variables are baked into the compiled JavaScript at
# build time (not read fresh at container start) -- see
# web_frontend/README.md's Configuration section. Passed as a Docker
# build ARG so it can be overridden at image-build time
# (`docker build --build-arg NEXT_PUBLIC_API_BASE_URL=...`) without
# editing this file. Defaults to the RELATIVE "/api/v1" path (see
# .env.sample and web_frontend/lib/api.ts) -- this is what makes the
# same built image work correctly regardless of which domain/port it
# ends up served from (localhost:8080 locally, a Railway domain in
# production): the browser only ever calls its OWN current origin,
# and Next.js's rewrites() proxy (see web_frontend/next.config.mjs)
# forwards that to FastAPI internally. Only override this build arg if
# you're intentionally NOT using the rewrites() proxy.
ARG NEXT_PUBLIC_API_BASE_URL=/api/v1
ENV NEXT_PUBLIC_API_BASE_URL=${NEXT_PUBLIC_API_BASE_URL}
RUN npm run build

# ---- Runtime stage ----
FROM python:3.11-slim AS runtime

# Nebula stores its SQLite DB at nebula.db (relative path, see
# core/database.py's default db_path="nebula.db") — WORKDIR doubles as
# where that file lands, so the named volume mounted here is what
# actually persists it (see docker-compose.yml). On Railway, mount a
# Railway Volume at the same path (or set DB_PATH) if you want the
# database to survive redeploys -- without one, each redeploy starts
# with a fresh, empty database, since Railway's own filesystem is
# ephemeral across deploys.
WORKDIR /app

# Node.js is installed in the RUNTIME image too (not just the builder
# stage) because main.py runs `npm run start` as a live subprocess for
# as long as the container runs -- that needs a working `node`/`npm`
# on PATH at runtime, not just at build time. `curl` is installed for
# the HEALTHCHECK below. This is NodeSource's official Debian/Ubuntu
# install method, matching python:3.11-slim's own Debian base.
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl \
        gnupg \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && apt-get purge -y gnupg \
    && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/*

# Non-root user: no reason for Nebula to run as root inside the
# container, and it never needs to bind privileged ports or touch the
# host filesystem outside its own volume.
RUN groupadd --gid 1000 nebula && \
    useradd --uid 1000 --gid nebula --shell /bin/bash --create-home nebula

# Bring in the Python wheels built in py-builder (installed to that
# stage's --user site-packages, then copied wholesale — avoids needing
# gcc/build tools in the final image at all).
COPY --from=py-builder /root/.local /home/nebula/.local

# Backend source.
COPY . .

# Bring in the ALREADY-BUILT frontend from frontend-builder: its
# node_modules (production + dev deps needed by `next start`) and its
# compiled .next/ output. This is exactly what web_frontend/README.md
# tells Sina to produce locally via `npm install && npm run build` --
# doing it here at image-build time means nobody who runs this Docker
# image ever needs to run that command by hand (unlike the bare-metal
# / non-Docker path, where that one-time step is still required — see
# README.md, unchanged for that case).
COPY --from=frontend-builder /build/web_frontend/node_modules ./web_frontend/node_modules
COPY --from=frontend-builder /build/web_frontend/.next ./web_frontend/.next
COPY --from=frontend-builder /build/web_frontend/public ./web_frontend/public
COPY --from=frontend-builder /build/web_frontend/package.json ./web_frontend/package.json
COPY --from=frontend-builder /build/web_frontend/next.config.mjs ./web_frontend/next.config.mjs

RUN chown -R nebula:nebula /app

USER nebula

# Matches --user pip installs going to ~/.local/bin — needed for any
# console-script entry points pulled in by dependencies.
ENV PATH="/home/nebula/.local/bin:${PATH}" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Port configuration:
# 8080: the Next.js frontend -- the ONLY port meant to be reached from
# outside the container. On Railway (or any platform that injects
# PORT), Next.js binds to PORT instead of 8080 automatically -- see
# web_frontend/package.json's "start" script and main.py's
# _resolve_public_port(). FastAPI (port 8000 by default) is
# intentionally NOT exposed here since v1.6.1 -- it's internal-only,
# reached only via Next.js's own rewrites() proxy over localhost.
EXPOSE 8080

# Confirms the single public port is actually up and accepting
# connections -- Railway (and `docker compose`) can use this signal
# to know the deploy succeeded rather than just "the process started".
# Uses the landing page ("/") rather than an API route since Next.js
# is what's actually bound to this port.
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD curl -f "http://localhost:${PORT:-8080}/" || exit 1

ENTRYPOINT ["python", "main.py"]