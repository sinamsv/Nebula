# syntax=docker/dockerfile:1

# Port configuration changes:
# - Set frontend exposed port to 8080.
# - Rationale: align with port 8080 standard.
# - How to revert: change NEXT_PUBLIC_API_BASE_URL back to 50051 and EXPOSE to 50080.

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
# actually ships/runs.
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
# editing this file, while still defaulting to the confirmed backend
# port (50051) for the common case of both services running in the
# same container/host.
ARG NEXT_PUBLIC_API_BASE_URL=http://localhost:8000/api/v1
ENV NEXT_PUBLIC_API_BASE_URL=${NEXT_PUBLIC_API_BASE_URL}
RUN npm run build

# ---- Runtime stage ----
FROM python:3.11-slim AS runtime

# Nebula stores its SQLite DB at nebula.db (relative path, see
# core/database.py's default db_path="nebula.db") — WORKDIR doubles as
# where that file lands, so the named volume mounted here is what
# actually persists it (see docker-compose.yml).
WORKDIR /app

# Node.js is installed in the RUNTIME image too (not just the builder
# stage) because web_ui_launcher.py runs `npm run start` as a live
# subprocess for as long as the container runs -- that needs a working
# `node`/`npm` on PATH at runtime, not just at build time. This is
# NodeSource's official Debian/Ubuntu install method, matching
# python:3.11-slim's own Debian base.
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl \
        gnupg \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && apt-get purge -y curl gnupg \
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
# README.md and web_ui_launcher.py's docstring, both unchanged for
# that case).
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
# 8000: the FastAPI backend — only meaningful when that adapter is running.
# 8080: the Next.js frontend — see web_frontend/package.json's "start" script, which binds here.
EXPOSE 8000
EXPOSE 8080

ENTRYPOINT ["python", "main.py"]
