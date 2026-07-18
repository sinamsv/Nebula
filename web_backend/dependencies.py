"""FastAPI dependency injection.

Two concerns live here:
1. Access to the shared core instances (db, auth, memory, coins,
   ai_handler, token cipher) constructed ONCE in main.py and handed to
   this app the same way discord_bot/client.py's build_bot() and
   telegram_bot/client.py's build_application() already receive them --
   see web_backend/app.py's create_app() for where these get attached
   to app.state.
2. JWT-based identity resolution: get_current_identity() is this
   adapter's equivalent of Discord's interaction.user.id / Telegram's
   update.effective_user.id -- except here it comes from a validated
   JWT's `sub` claim instead of a platform SDK object.

WEB_PLATFORM = "web": a web session is a platform_identities row with
platform="web", same shape as "discord"/"telegram" rows -- see the
design doc's "New web_user_id resolution path analogous to how
Discord/Telegram resolve platform_user_id" requirement. The
platform_user_id VALUE for a web identity is just the nebula_user_id
itself (as a string) -- there's no separate "web account id" the way
Discord/Telegram have their own native user ids; the web IS the
Nebula account here, so platform_user_id == str(nebula_user_id) by
convention, set once at signup/login time in the auth routes.
"""
from typing import Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from core.auth import AuthManager
from core.coins import CoinManager
from core.crypto import TokenCipher
from core.database import DatabaseManager
from core.memory import MemoryManager
from ai.handler import AIHandler
from web_backend.security import decode_access_token

WEB_PLATFORM = "web"

_bearer_scheme = HTTPBearer(auto_error=False)


def get_db(request: Request) -> DatabaseManager:
    return request.app.state.db


def get_auth(request: Request) -> AuthManager:
    return request.app.state.auth


def get_memory(request: Request) -> MemoryManager:
    return request.app.state.memory


def get_coin_manager(request: Request) -> CoinManager:
    return request.app.state.coin_manager


def get_ai_handler(request: Request) -> AIHandler:
    return request.app.state.ai_handler


def get_token_cipher(request: Request) -> TokenCipher:
    return request.app.state.token_cipher


async def get_current_identity(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer_scheme),
    auth: AuthManager = Depends(get_auth),
) -> dict:
    """Resolves the JWT on the request into a full identity dict
    (nebula_user_id, username, display_name, is_admin, is_approved) --
    the web equivalent of AuthManager.require_approved_identity() for
    Discord/Telegram, EXCEPT this one does NOT enforce is_approved by
    itself (see require_approved_identity_web() below for that) --
    some endpoints (e.g. checking your own pending-approval status)
    should work for an unapproved-but-logged-in user, so approval
    enforcement is a separate, explicit dependency rather than baked
    into every authenticated request."""
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid Authorization header. Expected: Bearer <token>.",
        )

    nebula_user_id = decode_access_token(credentials.credentials)
    if nebula_user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token. Please log in again.",
        )

    identity = auth.resolve_identity(WEB_PLATFORM, str(nebula_user_id))
    if identity is None:
        # Token is validly signed but no longer resolves to a linked
        # web identity (e.g. the account was deleted) -- treat exactly
        # like an invalid token rather than a 404, since from the
        # caller's perspective their session is simply no longer valid.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Account not found. Please log in again.",
        )

    return identity


async def require_approved_identity_web(
    identity: dict = Depends(get_current_identity),
) -> dict:
    """Stricter variant of get_current_identity() -- also enforces
    is_approved, mirroring AuthManager.require_approved_identity()'s
    behavior for Discord/Telegram. Use this (not get_current_identity
    directly) on any endpoint that should be blocked for a pending
    account, e.g. chat/coins endpoints -- but NOT on endpoints like
    "get my own approval status" which need to work precisely BECAUSE
    the account isn't approved yet."""
    if not identity['is_approved']:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="⏳ Your Nebula account is created but still pending admin approval.",
        )
    return identity


async def require_admin_identity_web(
    identity: dict = Depends(require_approved_identity_web),
) -> dict:
    """Admin-gated dependency for /admin/* routes -- mirrors
    discord_bot/admin_commands.py's AdminCommands._require_admin_identity()
    and discord_bot/coin_commands.py's add_coin_command's inline check."""
    if not identity['is_admin']:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="❌ Only Nebula admins can do that.",
        )
    return identity
