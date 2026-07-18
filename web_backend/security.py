"""JWT issuing + validation for the web adapter.

Library choice (confirmed): PyJWT, not python-jose. Reasoning: PyJWT is
actively maintained, has a smaller dependency footprint (no bundled
crypto backend choice to make -- it uses `cryptography` directly, which
this project already depends on for OAuth token encryption, see
core/crypto.py), and is the library FastAPI's own official docs example
uses for JWT auth. python-jose is a reasonable alternative but hasn't
seen a release in a long time relative to PyJWT, which matters for a
security-sensitive dependency.

Algorithm: HS256 (symmetric, single shared secret) -- this project has
no need for asymmetric JWT signing (no third party ever needs to verify
Nebula's tokens independently; only web_backend itself issues and
validates them), so RS256's added key-management complexity isn't
justified here. JWT_SECRET is a new required env var for the web
adapter (see .env.sample).

Design note mirroring core/auth.py's AuthError pattern: a small
JWTError-like flow, but implemented as returning None from
decode_access_token() on any failure (expired, malformed, wrong
signature) rather than a custom exception class -- callers
(get_current_identity() below) already need to turn "no valid token"
into a single 401 response regardless of WHICH validation step failed,
so a bool-ish return keeps that call site simpler than a multi-except
block would.
"""
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt

JWT_ALGORITHM = "HS256"
# 7 days: long enough that a logged-in web session doesn't nag the user
# to re-auth constantly (there is no refresh-token/rotation flow in
# this pass -- confirmed out of scope, matches the doc's "no server-
# side session store needed beyond what's required to validate/refresh
# tokens" language, which this simple long-lived-token approach
# satisfies without adding refresh-token infrastructure).
JWT_EXPIRY = timedelta(days=7)


def _get_secret() -> str:
    secret = os.getenv('JWT_SECRET')
    if not secret:
        raise RuntimeError(
            "JWT_SECRET is not set. Generate one with: "
            "python3 -c \"import secrets; print(secrets.token_urlsafe(64))\" "
            "and set it in .env."
        )
    return secret


def create_access_token(nebula_user_id: int) -> str:
    """Subject (`sub`) is the nebula_user_id as a string (JWT spec
    requires `sub` to be a string) -- this is the ONLY identity this
    token carries. Every other fact about the user (is_admin,
    is_approved, display_name, ...) is looked up fresh from the
    database on each request rather than embedded in the token, so an
    admin demotion or account rejection takes effect immediately on the
    next request instead of only once the old token expires."""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(nebula_user_id),
        "iat": now,
        "exp": now + JWT_EXPIRY,
    }
    return jwt.encode(payload, _get_secret(), algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> Optional[int]:
    """Returns the nebula_user_id encoded in the token, or None if the
    token is missing, expired, malformed, or has an invalid signature
    -- callers treat all of these identically (401 Unauthorized), so
    collapsing them to one Optional return keeps get_current_identity()
    simple."""
    try:
        payload = jwt.decode(token, _get_secret(), algorithms=[JWT_ALGORITHM])
        return int(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        return None
