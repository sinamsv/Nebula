"""Port and Web Gating Changes:
- Made web adapter mandatory: the `WEB_ENABLED` toggle is removed; the FastAPI web panel starts unconditionally.
- Backend port fallback: resolves `BACKEND_PORT`, then `WEB_PORT`, defaulting to `8000`.
- Rationale: simplify deployments by making the central web panel a core, mandatory system.
- How to revert: restore the WEB_ENABLED env checks and reset the port variables.

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
TELEGRAM_BOT_TOKEN / WEB_ENABLED is set in .env determines which
adapter(s) actually start. All three, some, or (if none are set)
none — with an explicit error in that last case rather than silently
doing nothing, matching this project's "explicit failure over silent
fallback" principle everywhere else (see core/auth.py, core/memory.py,
tools/search.py).

--- Web adapter addition ---

Confirmed with Sina: the web adapter (FastAPI + uvicorn, serving
web_backend/app.py's app) gets its own entry in this same asyncio.gather()
alongside Discord/Telegram, run as an in-process ASGI server via
uvicorn.Server rather than a separate `uvicorn web_backend.app:app`
process/command. This keeps the "one file you run: python main.py"
promise intact for the backend -- the ONLY separate process a person
running Nebula needs to think about is the Next.js frontend itself
(a genuinely different runtime, Node.js vs Python, which can't share
this event loop regardless), not the API server.

Gating: WEB_ENABLED=true (plus JWT_SECRET and OAUTH_TOKEN_ENCRYPTION_KEY,
both required for web_backend/app.py's create_app() to succeed) turns
the web adapter on, mirroring how DISCORD_TOKEN / TELEGRAM_BOT_TOKEN
already gate their adapters. WEB_PORT (default 8000) picks the port.
"""
import asyncio
import os

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


async def _start_web_adapter(db, auth, memory, coins, ai_handler):
    """Constructs web_backend's FastAPI app and serves it in-process via
    uvicorn.Server.serve() -- an awaitable coroutine, same shape as
    discord_client.start() and telegram_client.start(), so it slots
    into the same asyncio.gather() call below without needing its own
    event loop (uvicorn.run() would try to own the loop itself, which
    is exactly what discord_bot/client.py's start() docstring already
    explains must be avoided when multiple adapters share one loop)."""
    import uvicorn
    from web_backend.app import create_app

    app = create_app(db, auth, memory, coins, ai_handler)
    port = int(os.getenv('BACKEND_PORT', os.getenv('WEB_PORT', '8000')))
    config = uvicorn.Config(app, host="0.0.0.0", port=port, log_level="info")
    server = uvicorn.Server(config)
    print(f"Web adapter configured — starting on port {port}.")
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
    missing = [v for v in ('JWT_SECRET', 'OAUTH_TOKEN_ENCRYPTION_KEY') if not os.getenv(v)]
    if missing:
        print(
            f"ERROR: Web adapter is mandatory but {', '.join(missing)} "
            f"{'is' if len(missing) == 1 else 'are'} not set — web adapter cannot start. "
            "See .env.sample for how to generate these."
        )
    else:
        tasks.append(_start_web_adapter(db, auth, memory, coins, ai_handler))

    if not tasks:
        print(
            "ERROR: No platform adapters are running. Ensure that "
            "JWT_SECRET and OAUTH_TOKEN_ENCRYPTION_KEY are configured in your .env file "
            "so the mandatory web adapter can start."
        )
        return

    await asyncio.gather(*tasks)


if __name__ == "__main__":
    asyncio.run(main())
