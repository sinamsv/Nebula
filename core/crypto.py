"""Symmetric encryption for OAuth tokens (access_token / refresh_token).

Confirmed approach (matching the accompanying design doc): `cryptography`'s
Fernet, keyed from an env var (OAUTH_TOKEN_ENCRYPTION_KEY). This is
deliberately NOT bcrypt/hashing -- unlike password_hash in
core/auth.py, OAuth tokens must round-trip back to plaintext so Nebula
can actually present them to Google's APIs later. Fernet gives
authenticated symmetric encryption (AES-128-CBC + HMAC under the hood)
with a simple encrypt(bytes) -> bytes / decrypt(bytes) -> bytes API,
which is exactly what this narrow use case needs -- no public-key
infrastructure, no key rotation scheme, nothing beyond "store this
secret, get it back later, only Nebula's own process can do either."

Key handling:
- OAUTH_TOKEN_ENCRYPTION_KEY must be a Fernet-compatible key: 32
  url-safe base64-encoded bytes. Generate one with:
    python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
- Missing/invalid key is an explicit, named startup error (matching
  this project's "explicit failure over silent fallback" principle --
  see core/auth.py, core/memory.py, tools/search.py) -- NOT a silent
  fallback to storing tokens in plaintext, which would be a serious,
  silent security regression.
- Losing this key permanently loses the ability to decrypt any
  already-stored OAuth tokens (expected, standard trade-off for
  symmetric encryption -- documented in .env.sample). Since Google
  OAuth tokens can simply be re-issued by having the user reconnect,
  this is an acceptable trade-off for this use case (unlike, say,
  encrypted user file storage, where losing the key would be
  catastrophic).
"""
import os
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken


class CryptoError(Exception):
    """Raised for any encryption/decryption failure with a user-facing-
    safe-to-log message, mirroring core.auth.AuthError's role."""
    pass


class TokenCipher:
    """Thin wrapper around Fernet, constructed once (in main.py /
    web_backend's dependency setup) and reused for the process
    lifetime -- same pattern as every other shared instance in this
    project (DatabaseManager, AuthManager, etc.)."""

    def __init__(self, key: Optional[str] = None):
        raw_key = key or os.getenv('OAUTH_TOKEN_ENCRYPTION_KEY')
        if not raw_key:
            raise CryptoError(
                "OAUTH_TOKEN_ENCRYPTION_KEY is not set. Generate one with: "
                "python3 -c \"from cryptography.fernet import Fernet; "
                "print(Fernet.generate_key().decode())\" and set it in .env."
            )
        try:
            self._fernet = Fernet(raw_key.encode('utf-8'))
        except (ValueError, TypeError) as e:
            raise CryptoError(
                f"OAUTH_TOKEN_ENCRYPTION_KEY is not a valid Fernet key: {e}. "
                "It must be 32 url-safe base64-encoded bytes -- see this "
                "module's docstring for how to generate one."
            )

    def encrypt(self, plaintext: str) -> str:
        """Returns a url-safe string ciphertext, ready to store directly
        in oauth_connections.access_token / refresh_token (both TEXT
        columns)."""
        token_bytes = self._fernet.encrypt(plaintext.encode('utf-8'))
        return token_bytes.decode('utf-8')

    def decrypt(self, ciphertext: str) -> str:
        try:
            plaintext_bytes = self._fernet.decrypt(ciphertext.encode('utf-8'))
        except InvalidToken:
            raise CryptoError(
                "Failed to decrypt token -- either OAUTH_TOKEN_ENCRYPTION_KEY "
                "has changed since this token was stored, or the stored value "
                "is corrupted."
            )
        return plaintext_bytes.decode('utf-8')
