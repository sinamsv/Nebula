"""FastAPI app factory for the web adapter.

Structurally parallel to discord_bot/client.py's build_bot() and
telegram_bot/client.py's build_application(): this receives the shared
core instances (db, auth, memory, coin_manager, ai_handler) constructed
ONCE in main.py, plus a new TokenCipher for OAuth token encryption, and
attaches them to app.state so every route's dependency functions (see
web_backend/dependencies.py) can reach them without constructing their
own copies -- same sharing principle that makes cross-platform
identity/memory/coins actually work.

CORS: enabled broadly for local development (the Next.js frontend runs
on a different origin during dev, e.g. localhost:3000 vs the API's
own port). WEB_FRONTEND_URL is read for the OAuth callback's redirect
target (see web_backend/routes/auth.py) and doubles as the primary
allowed CORS origin; "*" is intentionally NOT used in production mode
since credentials (the Bearer token) are involved -- confirmed as a
reasonable default; Sina should tighten allow_origins to the actual
deployed frontend domain(s) in production .env.
"""
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.auth import AuthManager
from core.coins import CoinManager
from core.crypto import TokenCipher
from core.database import DatabaseManager
from core.memory import MemoryManager
from ai.handler import AIHandler

from web_backend.routes import admin, auth as auth_routes, chat, coins, sync


def create_app(
    db: DatabaseManager,
    auth: AuthManager,
    memory: MemoryManager,
    coin_manager: CoinManager,
    ai_handler: AIHandler,
) -> FastAPI:
    app = FastAPI(
        title="Nebula Web API",
        version="1.5.0",
        description="Web adapter for Nebula -- platform='web', thin HTTP layer over core/ and ai/.",
    )

    # TokenCipher is constructed HERE (not in main.py alongside the
    # other shared instances) since it's exclusively a web_backend/
    # concern today -- OAuth tokens are only ever written/read through
    # these HTTP routes, unlike db/auth/memory/coins which Discord and
    # Telegram also need. Raises CryptoError (uncaught, deliberately --
    # matches this project's "explicit failure over silent fallback"
    # principle) if OAUTH_TOKEN_ENCRYPTION_KEY is missing/invalid,
    # which fails web_backend's startup loudly rather than silently
    # storing OAuth tokens in plaintext or crashing later on first use.
    token_cipher = TokenCipher()

    app.state.db = db
    app.state.auth = auth
    app.state.memory = memory
    app.state.coin_manager = coin_manager
    app.state.ai_handler = ai_handler
    app.state.token_cipher = token_cipher

    frontend_url = os.getenv('WEB_FRONTEND_URL', 'http://localhost:3000')
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[frontend_url],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(auth_routes.router)
    app.include_router(chat.router)
    app.include_router(coins.router)
    app.include_router(sync.router)
    app.include_router(admin.router)

    @app.get("/api/v1/health")
    async def health():
        """Unauthenticated liveness check -- useful for Docker
        healthcheck directives and for the frontend to confirm the API
        is reachable before rendering auth-dependent UI."""
        return {"status": "ok", "ai_configured": ai_handler.provider is not None}

    return app
