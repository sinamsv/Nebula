# syntax=docker/dockerfile:1

# ---- Build stage: compile wheels so the final image doesn't need gcc/build tools ----
FROM python:3.11-slim AS builder

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc \
        libffi-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

# ---- Runtime stage ----
FROM python:3.11-slim AS runtime

# Nebula stores its SQLite DB at nebula.db (relative path, see
# core/database.py's default db_path="nebula.db") — WORKDIR doubles as
# where that file lands, so the named volume mounted here is what
# actually persists it (see docker-compose.yml).
WORKDIR /app

# Non-root user: no reason for Nebula to run as root inside the
# container, and it never needs to bind privileged ports or touch the
# host filesystem outside its own volume.
RUN groupadd --gid 1000 nebula && \
    useradd --uid 1000 --gid nebula --shell /bin/bash --create-home nebula

# Bring in the wheels built in the builder stage (installed to the
# builder's --user site-packages, then copied wholesale — avoids
# needing gcc/build tools in the final image at all).
COPY --from=builder /root/.local /home/nebula/.local

COPY . .

RUN chown -R nebula:nebula /app

USER nebula

# Matches --user pip installs going to ~/.local/bin — needed for any
# console-script entry points pulled in by dependencies.
ENV PATH="/home/nebula/.local/bin:${PATH}" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# No EXPOSE: Nebula is an outbound-only bot process (Discord gateway /
# Telegram long-polling), it doesn't listen on any port.

ENTRYPOINT ["python", "main.py"]
