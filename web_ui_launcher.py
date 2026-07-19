"""Port configuration changes:
- Frontend port: updated to 8080 (changed from 50080).
- Rationale: simplify and standardize.
- How to revert: change port references back to 50080.

Nebula web UI launcher — glue code to start the Next.js frontend
(web_frontend/) as a subprocess from main.py, alongside Discord,
Telegram, and the FastAPI web adapter.

WHY THIS FILE EXISTS AS A SEPARATE MODULE, NOT A DIRECT EDIT TO main.py:
main.py already exists as a finished, working file from a previous
session (see its own docstring — it constructs the shared core
instances and runs every configured adapter via asyncio.gather()).
Rather than guess at the exact current contents of that file and risk
overwriting something, this module is a small, self-contained,
drop-in addition. Wiring it in is a 3-line change to main.py — see
"HOW TO INTEGRATE THIS" at the bottom of this docstring.

WHAT THIS MODULE DOES:
_start_web_ui() is an async function with the exact same shape as
main.py's existing _start_web_adapter(): an awaitable coroutine meant
to be added to the same asyncio.gather(...) call that already starts
Discord/Telegram/the API. It uses asyncio.create_subprocess_exec (NOT
the blocking subprocess.run/subprocess.Popen) specifically so it
doesn't block the shared event loop the other adapters also run on —
matching the same reasoning discord_bot/client.py's start() and
telegram_bot/client.py's start() docstrings already give for why they
don't call asyncio.run() internally.

GATING:
Controlled by WEB_UI_ENABLED=true (mirrors how WEB_ENABLED already
gates the FastAPI backend adapter). Leaving it unset or false means
main.py behaves exactly as it does today — no frontend subprocess is
started, nothing else changes.

ONE-TIME SETUP REQUIRED BEFORE THIS WORKS (see the plain-English
summary in the chat response, and web_frontend/README.md, for the
full explanation aimed at Sina):
    cd web_frontend
    npm install
    npm run build

This module can start Node and run the already-built frontend, but it
cannot install Node's dependencies or compile the app for you the
first time — those are one-time, interactive-ish steps that need
network access to npm's registry and can take a minute or two, which
isn't appropriate to run silently as a side effect of every
`python main.py` launch. If node_modules/ or .next/ (the build output)
are missing, this module prints a clear, actionable error explaining
exactly which command to run, instead of letting Node itself produce a
cryptic "command not found" or "Could not find a production build"
failure.

PORTS: the frontend is started via `npm run start`, which (per
web_frontend/package.json's own "start" script) already binds to port
# 8080 — see web_frontend/package.json. Nothing in this module needs to
know the port number itself; it just runs the npm script.
"""
import asyncio
import os
import sys

# Relative to the repo root (where `python main.py` is run from) --
# matches the naming convention of discord_bot/, telegram_bot/,
# web_backend/ already in this project.
WEB_FRONTEND_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web_frontend")


def _frontend_prerequisites_missing() -> str | None:
    """Returns a human-readable reason the frontend can't be started
    yet, or None if everything needed is present. Checked BEFORE
    spawning the subprocess so the failure is a clear, actionable
    console message rather than Node's own cryptic error output (e.g.
    `next start` failing with "Could not find a production build in
    the '.next' directory" is exactly the kind of message that would
    otherwise confuse someone with zero Node/JS background, which the
    project's working style explicitly calls out Sina as having)."""
    if not os.path.isdir(WEB_FRONTEND_DIR):
        return (
            f"web_frontend/ directory not found at {WEB_FRONTEND_DIR}. "
            "Make sure the web_frontend folder from the frontend delivery "
            "has been placed at the root of the Nebula repository, "
            "alongside discord_bot/, telegram_bot/, and web_backend/."
        )

    node_modules_path = os.path.join(WEB_FRONTEND_DIR, "node_modules")
    if not os.path.isdir(node_modules_path):
        return (
            "web_frontend/node_modules is missing — dependencies haven't "
            "been installed yet. Run this ONE TIME:\n"
            "    cd web_frontend && npm install && npm run build"
        )

    build_output_path = os.path.join(WEB_FRONTEND_DIR, ".next")
    if not os.path.isdir(build_output_path):
        return (
            "web_frontend/.next (the production build output) is missing. "
            "Run this ONE TIME:\n"
            "    cd web_frontend && npm run build"
        )

    return None


async def _start_web_ui():
    """Awaitable coroutine, same shape as main.py's existing
    _start_web_adapter() — safe to add directly to the same
    asyncio.gather(...) call. Runs `npm run start` (the frontend's
    production server, bound to port 8080 per package.json) as a
    subprocess, and streams its stdout/stderr to this process's own
    console rather than silently swallowing frontend logs, so
    frontend errors are visible in the same place as every other
    adapter's output.
    """
    missing_reason = _frontend_prerequisites_missing()
    if missing_reason:
        print(f"ERROR: Web UI cannot start — {missing_reason}")
        print("Skipping the web UI subprocess; every other configured adapter will still start normally.")
        return

    print("Web UI configured — starting Next.js frontend on port 8080.")

    # npm.cmd on Windows, npm everywhere else -- asyncio.create_subprocess_exec
    # does NOT go through a shell by default (unlike subprocess.run with
    # shell=True), so the platform-specific executable name has to be
    # resolved explicitly here rather than relying on shell PATH lookup
    # + `&&` chaining the way a shell one-liner would.
    npm_executable = "npm.cmd" if sys.platform == "win32" else "npm"

    try:
        process = await asyncio.create_subprocess_exec(
            npm_executable, "run", "start",
            cwd=WEB_FRONTEND_DIR,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
    except FileNotFoundError:
        print(
            "ERROR: Could not find 'npm' on this system's PATH — Node.js "
            "doesn't appear to be installed. Install Node.js (which includes "
            "npm) from https://nodejs.org/, then run:\n"
            "    cd web_frontend && npm install && npm run build\n"
            "before starting Nebula again with WEB_UI_ENABLED=true."
        )
        return

    # Stream the subprocess's combined stdout/stderr line-by-line into
    # this process's own console, prefixed so it's identifiable amongst
    # Discord/Telegram/API log lines -- this is what "don't silently
    # swallow frontend logs" means concretely. Runs for as long as the
    # subprocess runs, which (for `npm run start`) is indefinitely,
    # keeping this coroutine "alive" inside asyncio.gather() the same
    # way discord_client.start() and telegram_client.start() stay alive
    # via their own blocking calls.
    assert process.stdout is not None
    async for raw_line in process.stdout:
        line = raw_line.decode(errors="replace").rstrip()
        print(f"[web_frontend] {line}")

    # If we get here, the subprocess exited (e.g. crashed, or was
    # killed externally) rather than this coroutine being cancelled --
    # surface that clearly instead of silently going quiet.
    returncode = await process.wait()
    print(f"WARNING: web_frontend subprocess exited unexpectedly (code {returncode}).")


# ---------------------------------------------------------------------
# HOW TO INTEGRATE THIS INTO main.py
# ---------------------------------------------------------------------
#
# 1. Save this file as `web_ui_launcher.py` at the repo root, alongside
#    main.py (NOT inside web_frontend/ or web_backend/).
#
# 2. In main.py, add one import near its other top-level imports:
#
#        import web_ui_launcher
#
# 3. In main.py's async def main(), find the existing block that
#    gates the FastAPI web adapter on WEB_ENABLED (search for
#    "web_enabled = os.getenv"). Immediately after that block (still
#    inside main(), still before `await asyncio.gather(*tasks)`), add:
#
#        web_ui_enabled = os.getenv('WEB_UI_ENABLED', '').strip().lower() in ('1', 'true', 'yes')
#        if web_ui_enabled:
#            tasks.append(web_ui_launcher._start_web_ui())
#        else:
#            print("WEB_UI_ENABLED not set — Web UI disabled.")
#
#    That's the entire integration: it follows the exact same
#    "gate on an env var, append an awaitable coroutine to `tasks`"
#    pattern main.py already uses for discord_token, telegram_token,
#    and web_enabled immediately above it — no changes to
#    asyncio.gather(*tasks) itself are needed, since it already just
#    unpacks whatever is in `tasks`.
#
# 4. Add WEB_UI_ENABLED=false to .env.sample's web-panel section
#    (right next to the existing WEB_ENABLED=false), documented as:
#    "Set to true to also launch the Next.js frontend automatically as
#    part of `python main.py` — requires a one-time
#    `cd web_frontend && npm install && npm run build` first (see
#    web_frontend/README.md)."
#
# That's it — no other part of main.py needs to change. Discord,
# Telegram, and the FastAPI backend adapter all start exactly as they
# do today regardless of this variable.
