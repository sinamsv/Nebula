"""POST /auth/signup, POST /auth/login, GET /auth/google,
GET /auth/google/callback.

Thin adapter over core.auth.AuthManager -- same "thin adapters, fat
core" principle already used by discord_bot/auth_commands.py and
telegram_bot/auth_handlers.py. This is the third sibling of those two
files, just speaking HTTP/JSON instead of Discord slash commands or
Telegram bot commands.

WEB_PLATFORM identity convention: platform_user_id for a web identity
is str(nebula_user_id) -- see web_backend/dependencies.py's module
docstring for why. This means signup/login here link_platform_identity
using the nebula_user_id that was JUST created/resolved, not some
separate web-session id, which is what makes get_current_identity()'s
JWT-sub-is-nebula_user_id design self-consistent.
"""
import os
import secrets
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse

from core.auth import AuthError, AuthManager
from core.crypto import TokenCipher
from core.database import DatabaseManager
from web_backend.dependencies import WEB_PLATFORM, get_auth, get_db, get_token_cipher
from web_backend.schemas.auth import (
    BootstrapStatusResponse,
    LoginRequest,
    LoginResponse,
    SignupRequest,
    SignupResponse,
)
from web_backend.security import create_access_token

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"
GOOGLE_OAUTH_SCOPES = "openid email profile"

# In-memory CSRF state store for the OAuth redirect round-trip.
# Confirmed as sufficient for this pass: the state token only needs to
# survive one browser redirect round-trip (seconds, not days -- unlike
# platform_sync_codes, which are deliberately persisted to survive
# across a slower cross-platform hand-off). A single-process deployment
# is assumed for now, same assumption the rest of this project already
# makes (SQLite, no distributed cache) -- if Nebula's web_backend is
# ever run as multiple processes/replicas, this would need to move to
# the database or a shared cache, flagged here rather than silently
# left as a latent bug.
_oauth_state_store: dict = {}


@router.get("/bootstrap-status", response_model=BootstrapStatusResponse)
async def bootstrap_status(db: DatabaseManager = Depends(get_db)):
    """Public, no-auth endpoint the signup page calls to decide whether
    to render the 'I'm admin' checkbox at all -- see the design doc's
    explicit requirement that the checkbox be hidden entirely (not just
    fail at submit time) once bootstrap is claimed."""
    return BootstrapStatusResponse(bootstrap_available=not db.is_bootstrap_claimed())


@router.post("/signup", response_model=SignupResponse)
async def signup(body: SignupRequest, auth: AuthManager = Depends(get_auth)):
    display_name = body.display_name or body.username
    try:
        # platform_user_id is a placeholder here because AuthManager.signup()
        # needs SOME platform_user_id to link immediately, but the real
        # nebula_user_id doesn't exist until create_user() runs inside
        # signup() itself -- so we can't know str(nebula_user_id) in
        # advance the way discord/telegram's adapters can (they already
        # have their platform's own native id before calling signup()).
        # Passing username here as a temporary linking key, then
        # immediately re-linking with the real nebula_user_id below, is
        # NOT viable either (link_platform_identity would just fail on
        # the id mismatch on the second call). Instead: call signup()
        # with platform_user_id left as a sentinel, then fix up the
        # platform_identities row afterward using the now-known
        # nebula_user_id. This two-step approach costs one extra DB
        # write on the signup path only (not on every login), which is
        # an acceptable, one-time cost given the alternative is either
        # a chicken-and-egg problem or duplicating create_user()'s logic
        # here just to get the id first.
        result = auth.signup(
            username=body.username,
            password=body.password,
            display_name=display_name,
            platform=WEB_PLATFORM,
            platform_user_id="__pending__",
            platform_display_name=display_name,
            bootstrap_key=body.bootstrap_key,
        )
    except AuthError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    # Fix up the sentinel platform_user_id to the real, now-known
    # nebula_user_id -- see the long comment above for why this is a
    # two-step process specifically for web signup.
    auth.db.link_platform_identity(
        WEB_PLATFORM, str(result['nebula_user_id']), result['nebula_user_id'], display_name
    )
    # The sentinel row is superseded by ON CONFLICT DO UPDATE inside
    # link_platform_identity() only if the (platform, platform_user_id)
    # PRIMARY KEY matches -- it doesn't here (different platform_user_id
    # values), so the sentinel row is deleted explicitly to avoid
    # leaving an orphaned, never-loginable platform_identities row
    # behind for every web signup.
    _delete_sentinel_identity(auth.db, result['nebula_user_id'])

    token = create_access_token(result['nebula_user_id'])
    return SignupResponse(
        nebula_user_id=result['nebula_user_id'],
        username=result['username'],
        is_approved=result['is_approved'],
        became_admin=result['became_admin'],
        access_token=token,
    )


def _delete_sentinel_identity(db: DatabaseManager, nebula_user_id: int):
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "DELETE FROM platform_identities WHERE platform = ? AND platform_user_id = '__pending__' "
        "AND nebula_user_id = ?",
        (WEB_PLATFORM, nebula_user_id),
    )
    conn.commit()
    conn.close()


@router.post("/login", response_model=LoginResponse)
async def login(body: LoginRequest, auth: AuthManager = Depends(get_auth)):
    try:
        # For login, unlike signup, the nebula_user_id already exists
        # (it's an existing account) -- but we still don't know it
        # until AFTER get_user_by_username() resolves inside login().
        # AuthManager.login() links using whatever platform_user_id is
        # passed in, so the same "pass a placeholder, fix up after"
        # approach is needed here too, for exactly the same reason as
        # signup() above.
        result = auth.login(
            username=body.username,
            password=body.password,
            platform=WEB_PLATFORM,
            platform_user_id="__pending__",
            platform_display_name=body.username,
        )
    except AuthError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))

    auth.db.link_platform_identity(
        WEB_PLATFORM, str(result['nebula_user_id']), result['nebula_user_id'], body.username
    )
    _delete_sentinel_identity(auth.db, result['nebula_user_id'])

    token = create_access_token(result['nebula_user_id'])
    return LoginResponse(
        nebula_user_id=result['nebula_user_id'],
        username=result['username'],
        is_approved=result['is_approved'],
        is_admin=result['is_admin'],
        access_token=token,
    )


# ------------------------------------------------------------------
# Google OAuth (infrastructure only -- see core/crypto.py and
# oauth_connections table. Not wired to any tool this release.)
# ------------------------------------------------------------------

def _google_oauth_configured() -> bool:
    return bool(
        os.getenv('GOOGLE_OAUTH_CLIENT_ID')
        and os.getenv('GOOGLE_OAUTH_CLIENT_SECRET')
        and os.getenv('GOOGLE_OAUTH_REDIRECT_URI')
    )


@router.get("/google")
async def google_oauth_start():
    """Redirects to Google's OAuth consent screen. Optional/skippable
    by design (confirmed): this endpoint existing and working has no
    bearing on whether signup/login/chat work, since Google OAuth is
    infrastructure-only this release, not a login method."""
    if not _google_oauth_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google OAuth is not configured on this Nebula instance.",
        )

    state = secrets.token_urlsafe(32)
    _oauth_state_store[state] = True

    params = {
        "client_id": os.getenv('GOOGLE_OAUTH_CLIENT_ID'),
        "redirect_uri": os.getenv('GOOGLE_OAUTH_REDIRECT_URI'),
        "response_type": "code",
        "scope": GOOGLE_OAUTH_SCOPES,
        "access_type": "offline",  # required to get a refresh_token back
        "prompt": "consent",
        "state": state,
    }
    return RedirectResponse(url=f"{GOOGLE_AUTH_URL}?{urlencode(params)}")


@router.get("/google/callback")
async def google_oauth_callback(
    request: Request,
    code: str = None,
    state: str = None,
    error: str = None,
    auth: AuthManager = Depends(get_auth),
    db: DatabaseManager = Depends(get_db),
    cipher: TokenCipher = Depends(get_token_cipher),
):
    """Handles Google's redirect back, exchanges the code for tokens,
    stores them ENCRYPTED against the caller's nebula_user_id, and
    issues/confirms the app's own JWT.

    Identity linkage note: this callback has no prior request context
    telling it WHICH Nebula account initiated the flow (Google's
    redirect only carries back what WE sent it: code + our own state
    token). Two realistic flows exist for "whose account do these
    Google tokens belong to":
      (a) an already-logged-in web user clicks 'Connect Google' from
          their dashboard -- their existing JWT should ideally travel
          through the OAuth round-trip.
      (b) Google Sign-In is used AS a login/signup method itself.
    This pass implements (b) as the primary path (matches the
    confirmed endpoint list: /auth/google + /auth/google/callback
    living under /auth, alongside signup/login, not under a
    /users/me/connections path) -- a Google account's verified email
    is used to find-or-create a Nebula account, then an app JWT is
    issued exactly like signup/login above. This is flagged explicitly
    to Sina as a design point worth confirming: if the intent was
    actually (a) -- linking Google to an ALREADY-authenticated
    session, purely for future Sheets/Calendar tool access, without
    Google ever being a login method -- the state parameter would need
    to carry the initiating session's identity through the round-trip
    instead. Implemented as (b) for now since it's the simpler,
    self-contained flow and satisfies 'get a user through the OAuth
    flow and have their tokens land safely in oauth_connections'
    exactly as specified either way; revisit if (a) was actually
    intended.
    """
    if error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Google OAuth error: {error}")
    if not code or not state:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing code or state parameter.")
    if state not in _oauth_state_store:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired OAuth state.")
    del _oauth_state_store[state]

    async with httpx.AsyncClient() as client:
        token_response = await client.post(GOOGLE_TOKEN_URL, data={
            "code": code,
            "client_id": os.getenv('GOOGLE_OAUTH_CLIENT_ID'),
            "client_secret": os.getenv('GOOGLE_OAUTH_CLIENT_SECRET'),
            "redirect_uri": os.getenv('GOOGLE_OAUTH_REDIRECT_URI'),
            "grant_type": "authorization_code",
        })
        if token_response.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Failed to exchange code with Google: {token_response.text}",
            )
        token_data = token_response.json()

        userinfo_response = await client.get(
            GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {token_data['access_token']}"},
        )
        if userinfo_response.status_code != 200:
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Failed to fetch Google user info.")
        userinfo = userinfo_response.json()

    google_email = userinfo.get("email")
    if not google_email:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Google did not return an email address.")

    # Find-or-create: does a Nebula account already exist for this
    # Google identity? Uses platform_identities with platform="google"
    # (distinct from platform="web") so a Google-authenticated session
    # is tracked separately from a password-based web session, even
    # though both ultimately resolve to the same nebula_user_id once
    # linked.
    identity = auth.resolve_identity("google", google_email)
    if identity is None:
        username_base = google_email.split("@")[0]
        username = _unique_username(db, username_base)
        random_password = secrets.token_urlsafe(24)  # unusable password; Google Sign-In is the only login path for this account unless they later set one
        import bcrypt
        password_hash = bcrypt.hashpw(random_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        nebula_user_id = db.create_user(username, password_hash, userinfo.get("name", username))
        db.link_platform_identity("google", google_email, nebula_user_id, userinfo.get("name"))
        nebula_user_id_final = nebula_user_id
    else:
        nebula_user_id_final = identity['nebula_user_id']

    # Store the OAuth tokens themselves, ENCRYPTED -- this is the part
    # that's actually "infrastructure for future Sheets/Calendar tools"
    # per the design doc; nothing above this point is new infra, it's
    # just find-or-create-account plumbing reusing existing patterns.
    access_token_enc = cipher.encrypt(token_data['access_token'])
    refresh_token_enc = cipher.encrypt(token_data['refresh_token']) if 'refresh_token' in token_data else None
    expires_in = token_data.get('expires_in')
    from datetime import datetime, timedelta, timezone
    expires_at = (datetime.now(timezone.utc) + timedelta(seconds=expires_in)).isoformat() if expires_in else None

    db.upsert_oauth_connection(
        nebula_user_id=nebula_user_id_final,
        provider="google",
        access_token_encrypted=access_token_enc,
        refresh_token_encrypted=refresh_token_enc,
        expires_at=expires_at,
        scopes=token_data.get('scope', GOOGLE_OAUTH_SCOPES),
    )

    app_token = create_access_token(nebula_user_id_final)
    frontend_url = os.getenv('WEB_FRONTEND_URL', 'http://localhost:3000')
    return RedirectResponse(url=f"{frontend_url}/oauth/complete?token={app_token}")


def _unique_username(db: DatabaseManager, base: str) -> str:
    """Google emails can collide with existing usernames or contain
    characters outside USERNAME_PATTERN (e.g. dots) -- sanitize and
    disambiguate rather than letting create_user() fail on a
    UNIQUE-constraint collision with no recovery path in this flow."""
    import re
    sanitized = re.sub(r'[^a-zA-Z0-9_]', '_', base)[:24] or "user"
    candidate = sanitized
    suffix = 0
    while db.get_user_by_username(candidate):
        suffix += 1
        candidate = f"{sanitized}_{suffix}"
    return candidate
