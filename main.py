"""Railway / PaaS Deployment Changes (v1.6.1):
- Single public port: PaaS platforms like Railway inject a `PORT` env var and only expose
  THAT port publicly. Next.js (the frontend) now binds to `PORT` (default 8080 for local/
  non-PaaS use) since it's the thing that needs to be reachable from the outside world.
- FastAPI becomes an internal-only service: it always binds to `BACKEND_PORT` (default 8000)
  on 127.0.0.1 -- never exposed directly. The browser never talks to it directly either;
  see web_frontend/next.config.mjs's new rewrites() block, which proxies /api/v1/* from
  Next.js straight to FastAPI over localhost. This sidesteps Railway's one-public-port
  constraint without needing a second Railway service or an nginx layer.
- Runtime npm install/build REMOVED: this used to check for missing node_modules/.next and
  install/build them at process startup, which does not work well on PaaS (ephemeral/
  read-only-ish filesystems, slow cold starts, healthcheck timeouts while npm installs).
  The build is now expected to have already happened in the Docker image (see Dockerfile's
  frontend-builder stage, unchanged) -- main.py's job here is just to START the already-built
  frontend with `npm run start`, nothing more. Local (non-Docker) development still needs the
  one-time `npm install && npm run build` described in web_frontend/README.md -- that hasn't
  changed, only the automatic "do it for you at every startup" behavior is gone.
- Explicit 0.0.0.0 bind for Next.js: `next start -p <port> -H 0.0.0.0` -- Next's default host
  binding (localhost) is not reachable from outside a container even if the port is correct.
- How to revert: restore the old _should_install_deps/_update_last_installed_state/build-check
  block inside _start_web_ui(), and go back to reading BACKEND_PORT/WEB_PORT only (no PORT
  fallback) for whichever service you want to expose.

Nebula — top-level launcher.

This is the ONE file you run: `python main.py`.

All three platform adapters (Discord, Telegram, Web) share a single set
of core.database/auth/memory/coins instances and a single
ai.handler.AIHandler, all constructed exactly once here. That sharing is
what makes identity, memory, and coin balance genuinely cross-platform:
a message sent via Telegram and a message sent via Discord (or the web
panel) for the SAME Nebula account read and write through the exact
same objects, not siloed copies of the same sqlite file.

Each adapter is independently optional: whichever of DISCORD_TOKEN /
TELEGRAM_BOT_TOKEN is set in .env determines which adapter(s) actually
start. The web adapter (FastAPI + Next.js) is mandatory and always
starts. Explicit error if literally nothing can start, rather than
silently doing nothing, matching this project's "explicit failure over
silent fallback" principle everywhere else (see core/auth.py,
core/memory.py, tools/search.py).

--- Web adapter addition ---

The web adapter (FastAPI + uvicorn, serving web_backend/app.py's app)
gets its own entry in this same asyncio.gather() alongside Discord/
Telegram, run as an in-process ASGI server via uvicorn.Server rather
than a separate `uvicorn web_backend.app:app` process/command. This
keeps the "one file you run: python main.py" promise intact for the
backend -- the ONLY separate process a person running Nebula needs to
think about is the Next.js frontend itself (a genuinely different
runtime, Node.js vs Python, which can't share this event loop
regardless), not the API server.

Since v1.6.1, FastAPI is internal-only (127.0.0.1:BACKEND_PORT) and
Next.js is the single public-facing process, proxying API calls to
FastAPI itself via next.config.mjs's rewrites -- see the module
docstring above for the full rationale.
"""
import asyncio
import os
import sys

from dotenv import load_dotenv

load_dotenv()

from core.database import DatabaseManager
from core.auth import AuthManager
from core.memory import MemoryManager
from core.coins import CoinManager
from tools.search import SearchTool
from ai.handler import AIHandler

import discord_bot.client as discord_client
import telegram_bot.client as telegram_client


def _resolve_internal_backend_port() -> int:
    """FastAPI's port. Since v1.6.1 this is NEVER the publicly exposed
    port on PaaS -- it only needs to be reachable from Next.js's own
    rewrites() proxy, which runs in the same container over
    localhost. Defaults to 8000, unchanged from before."""
    return int(os.getenv('BACKEND_PORT', os.getenv('WEB_PORT', '8000')))


async def _start_web_adapter(db, auth, memory, coins, ai_handler, internal_port: int):
    """Constructs web_backend's FastAPI app and serves it in-process via
    uvicorn.Server.serve() -- an awaitable coroutine, same shape as
    discord_client.start() and telegram_client.start(), so it slots
    into the same asyncio.gather() call below without needing its own
    event loop.

    Since v1.6.1: bound to 127.0.0.1 only, not 0.0.0.0. FastAPI is no
    longer meant to be reachable from outside the container directly
    -- Next.js's rewrites() proxy (see web_frontend/next.config.mjs)
    is the only thing that talks to it, over localhost, from inside
    the same container. This is what lets one Railway service (one
    public port) serve both the API and the UI without a second
    service or a separate reverse-proxy process.
    """
    import uvicorn
    from web_backend.app import create_app

    app = create_app(db, auth, memory, coins, ai_handler)
    config = uvicorn.Config(app, host="127.0.0.1", port=internal_port, log_level="info")
    server = uvicorn.Server(config)
    print(f"Web adapter configured — starting internally on 127.0.0.1:{internal_port} (not publicly exposed).")
    await server.serve()


async def main():
    # DB_PATH lets the Docker image point nebula.db at a mounted volume
    # (see docker-compose.yml's DB_PATH=/app/data/nebula.db) instead of
    # the container's ephemeral filesystem. Defaults to "nebula.db"
    # (relative to CWD), unchanged from before, for anyone running
    # main.py directly outside Docker.
    db = DatabaseManager(db_path=os.getenv('DB_PATH', 'nebula.db'))
    auth = AuthManager(db)
    memory = MemoryManager(db)
    coins = CoinManager(db)
    search_tool = SearchTool()
    ai_handler = AIHandler(db, auth, memory, coins, search_tool)

    tasks = []

    discord_token = os.getenv('DISCORD_TOKEN')
    if discord_token:
        bot = discord_client.build_bot(db, auth, memory, coins, search_tool, ai_handler)
        tasks.append(discord_client.start(bot, discord_token))
        print("Discord adapter configured — starting.")
    else:
        print("DISCORD_TOKEN not set — Discord adapter disabled.")

    telegram_token = os.getenv('TELEGRAM_BOT_TOKEN')
    if telegram_token:
        application = telegram_client.build_application(
            db, auth, memory, coins, search_tool, ai_handler, telegram_token
        )
        tasks.append(telegram_client.start(application))
        print("Telegram adapter configured — starting.")
    else:
        print("TELEGRAM_BOT_TOKEN not set — Telegram adapter disabled.")

    # Web adapter is mandatory. Always initialize web features unconditionally.
    internal_backend_port = _resolve_internal_backend_port()

    missing = [v for v in ('JWT_SECRET', 'OAUTH_TOKEN_ENCRYPTION_KEY') if not os.getenv(v)]
    if missing:
        print(
            f"ERROR: Web adapter is mandatory but {', '.join(missing)} "
            f"{'is' if len(missing) == 1 else 'are'} not set — web adapter cannot start. "
            "See .env.sample for how to generate these."
        )
        sys.exit(1)
    else:
        tasks.append(_start_web_adapter(db, auth, memory, coins, ai_handler, internal_backend_port))

    if not tasks:
        print(
            "ERROR: No platform adapters are running. Ensure that "
            "JWT_SECRET and OAUTH_TOKEN_ENCRYPTION_KEY are configured in your .env file "
            "so the mandatory web adapter can start."
        )
        sys.exit(1)

    loop = asyncio.get_running_loop()
    shutdown_event = asyncio.Event()

    def handle_signal():
        print("Received termination signal. Triggering graceful shutdown...")
        shutdown_event.set()

    if sys.platform != "win32":
        import signal
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, handle_signal)
            except Exception as e:
                print(f"Warning: could not register signal handler for {sig}: {e}")

    async def run_gather():
        await asyncio.gather(*tasks)

    gather_task = asyncio.create_task(run_gather())
    shutdown_task = asyncio.create_task(shutdown_event.wait())

    try:
        if sys.platform != "win32":
            await asyncio.wait(
                [gather_task, shutdown_task],
                return_when=asyncio.FIRST_COMPLETED
            )
            if shutdown_event.is_set():
                print("Graceful shutdown initiated. Cancelling active tasks...")
                gather_task.cancel()
                try:
                    await gather_task
                except asyncio.CancelledError:
                    pass
        else:
            await gather_task
    except asyncio.CancelledError:
        gather_task.cancel()
        try:
            await gather_task
        except asyncio.CancelledError:
            pass
        raise
    finally:
        if not gather_task.done():
            gather_task.cancel()
            try:
                await gather_task
            except Exception:
                pass
        print("All processes cleaned up. Exiting main.")


if __name__ == "__main__":
    asyncio.run(main())
