import os
import re
import secrets
import bcrypt
from typing import Dict, Optional
from core.database import DatabaseManager


USERNAME_PATTERN = re.compile(r'^[a-zA-Z0-9_]{3,32}$')
MIN_PASSWORD_LENGTH = 8

# --- Cross-platform account sync (see generate_sync_code / verify_sync_code) ---
SYNC_CODE_LENGTH = 6
SYNC_CODE_EXPIRY_MINUTES = 10


class AuthError(Exception):
    """Raised for any auth failure with a user-facing message. Cogs should
    catch this and send str(e) back to the user rather than a stack trace."""
    pass


class AuthManager:
    """Platform-agnostic authentication and account management.

    Design principles (matching the rest of the codebase):
    - Explicit failure over silent fallback: bad input raises AuthError
      with a specific reason, never fails silently or falls back to a
      default account.
    - Not approved does not mean invisible: an unapproved user gets a
      clear "pending approval" message, not treated as if they don't
      have an account at all.
    """

    def __init__(self, db: DatabaseManager):
        self.db = db
        self.bootstrap_api_key = os.getenv('ADMIN_BOOTSTRAP_KEY')

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def _validate_username(self, username: str):
        if not USERNAME_PATTERN.match(username):
            raise AuthError(
                "❌ Invalid username. Use 3-32 characters: letters, numbers, "
                "and underscores only."
            )

    def _validate_password(self, password: str):
        if len(password) < MIN_PASSWORD_LENGTH:
            raise AuthError(
                f"❌ Password too short. Use at least {MIN_PASSWORD_LENGTH} characters."
            )

    # ------------------------------------------------------------------
    # Signup / Login
    # ------------------------------------------------------------------

    def signup(self, username: str, password: str, display_name: str,
               platform: str, platform_user_id: str,
               platform_display_name: str = None,
               bootstrap_key: Optional[str] = None) -> Dict:
        """Create a new Nebula account and link the calling platform
        identity to it immediately (so the person doesn't have to sign up
        then separately log in on the same platform).

        If bootstrap_key is provided and matches ADMIN_BOOTSTRAP_KEY, and
        the bootstrap slot hasn't been claimed yet, this account becomes
        the first admin and is auto-approved. Otherwise the account is
        created unapproved and pending review.

        Returns a dict describing the outcome. Raises AuthError on bad
        input or a taken username.
        """
        self._validate_username(username)
        self._validate_password(password)

        if self.db.get_user_by_username(username):
            raise AuthError(f"❌ Username **{username}** is already taken. Try another.")

        password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        nebula_user_id = self.db.create_user(username, password_hash, display_name)
        if nebula_user_id is None:
            raise AuthError(f"❌ Username **{username}** is already taken. Try another.")

        linked = self.db.link_platform_identity(
            platform, platform_user_id, nebula_user_id, platform_display_name
        )
        if not linked:
            raise AuthError(
                "❌ Account was created but could not be linked to this platform "
                "identity — it's already linked to a different Nebula account. "
                "Contact an admin."
            )

        became_admin = False
        if bootstrap_key is not None:
            became_admin = self._try_bootstrap_admin(nebula_user_id, bootstrap_key)

        if became_admin:
            return {
                'nebula_user_id': nebula_user_id,
                'username': username,
                'became_admin': True,
                'is_approved': True,
            }

        return {
            'nebula_user_id': nebula_user_id,
            'username': username,
            'became_admin': False,
            'is_approved': False,
        }

    def _try_bootstrap_admin(self, nebula_user_id: int, bootstrap_key: str) -> bool:
        if not self.bootstrap_api_key:
            return False
        if bootstrap_key != self.bootstrap_api_key:
            return False
        if self.db.is_bootstrap_claimed():
            return False

        won = self.db.try_claim_bootstrap(nebula_user_id)
        if not won:
            return False

        self.db.set_user_admin(nebula_user_id, True)
        self.db.set_user_approval(nebula_user_id, True, approved_by=nebula_user_id)
        self.db.log_admin_action(
            nebula_user_id, self._display_name_or_username(nebula_user_id),
            "bootstrap_admin_claimed", nebula_user_id,
            self._display_name_or_username(nebula_user_id),
            "Claimed one-time ADMIN_BOOTSTRAP_KEY to become first admin"
        )
        return True

    def _display_name_or_username(self, nebula_user_id: int) -> str:
        user = self.db.get_user_by_id(nebula_user_id)
        return user['display_name'] if user else str(nebula_user_id)

    def login(self, username: str, password: str, platform: str,
              platform_user_id: str, platform_display_name: str = None) -> Dict:
        """Verify credentials and link the calling platform identity to the
        matched Nebula account. Raises AuthError on any failure — wrong
        username, wrong password, or the platform identity already
        belonging to someone else."""
        user = self.db.get_user_by_username(username)
        if not user:
            raise AuthError("❌ Incorrect username or password.")

        if not bcrypt.checkpw(password.encode('utf-8'), user['password_hash'].encode('utf-8')):
            raise AuthError("❌ Incorrect username or password.")

        linked = self.db.link_platform_identity(
            platform, platform_user_id, user['nebula_user_id'], platform_display_name
        )
        if not linked:
            raise AuthError(
                "❌ This platform account is already linked to a different "
                "Nebula account. Contact an admin if this seems wrong."
            )

        return {
            'nebula_user_id': user['nebula_user_id'],
            'username': user['username'],
            'is_approved': user['is_approved'],
            'is_admin': user['is_admin'],
        }

    # ------------------------------------------------------------------
    # Cross-platform account linking (sync codes)
    # ------------------------------------------------------------------
    #
    # Direction is deliberately fixed: the code is ISSUED on a platform
    # where the account is already linked (today: Discord, via /sync),
    # and CONSUMED on the new platform (today: Telegram, via /verify).
    # This is not symmetric/pluggable in either direction per call — it
    # can't be, because Telegram (and most bot platforms) won't let a bot
    # message a user_id it hasn't received an inbound message from yet.
    # A future third platform reuses verify_sync_code() the same way
    # Telegram does; generate_sync_code() is called from whichever
    # already-linked platform the user is issuing the code FROM.

    def generate_sync_code(self, nebula_user_id: int, target_platform: str) -> str:
        """Generate a one-time numeric code so this Nebula account can be
        linked to a platform identity on `target_platform` without that
        platform's bot needing to message the user first. Any
        previously-issued, still-unconsumed code for this
        (nebula_user_id, target_platform) pair is invalidated — only the
        most recently generated code is ever valid, so running /sync
        twice by mistake doesn't leave two "live" codes to be confused
        about."""
        code = f"{secrets.randbelow(10 ** SYNC_CODE_LENGTH):0{SYNC_CODE_LENGTH}d}"
        self.db.create_sync_code(nebula_user_id, target_platform, code)
        return code

    def verify_sync_code(self, username: str, code: str, target_platform: str,
                          platform_user_id: str, platform_display_name: str = None) -> Dict:
        """Consume a sync code generated by generate_sync_code() and link
        platform_user_id (on target_platform) to the Nebula account that
        issued it.

        Called from the NEW platform's side, where — unlike every other
        AuthManager method — there is no existing linked session to
        resolve identity from. That's why `username` is a required,
        explicit input here: it's the only thing available to look up
        which account this code belongs to."""
        target = self.db.get_user_by_username(username)
        if not target:
            raise AuthError(f"❌ No Nebula account found with username **{username}**.")

        pending = self.db.get_valid_sync_code(
            target['nebula_user_id'], target_platform, SYNC_CODE_EXPIRY_MINUTES
        )
        if pending is None:
            raise AuthError(
                "❌ No active sync code found for that account. Generate a "
                "new one and try again — codes expire after "
                f"{SYNC_CODE_EXPIRY_MINUTES} minutes."
            )
        if pending['code'] != code:
            raise AuthError("❌ Incorrect code. Double-check and try again.")

        linked = self.db.link_platform_identity(
            target_platform, platform_user_id, target['nebula_user_id'], platform_display_name
        )
        if not linked:
            raise AuthError(
                "❌ This platform account is already linked to a different "
                "Nebula account. Contact an admin if this seems wrong."
            )

        # Only mark the code consumed AFTER the link succeeds, so a
        # failed link (already-linked-elsewhere case above) leaves the
        # code intact for a retry rather than burning it on a failure.
        self.db.consume_sync_code(pending['id'])

        return {
            'nebula_user_id': target['nebula_user_id'],
            'username': target['username'],
            'is_approved': target['is_approved'],
            'is_admin': target['is_admin'],
        }

    # ------------------------------------------------------------------
    # Identity resolution (used by every message-handling path)
    # ------------------------------------------------------------------

    def resolve_identity(self, platform: str, platform_user_id: str) -> Optional[Dict]:
        return self.db.get_nebula_user_for_platform_identity(platform, platform_user_id)

    def require_approved_identity(self, platform: str, platform_user_id: str) -> Dict:
        identity = self.resolve_identity(platform, platform_user_id)
        if identity is None:
            raise AuthError(
                "❌ You need a Nebula account to do that. Use `/signup` to "
                "create one or `/login` if you already have one."
            )
        if not identity['is_approved']:
            raise AuthError(
                "⏳ Your Nebula account is created but still pending admin "
                "approval. You'll be able to use Nebula once an admin "
                "approves you."
            )
        return identity

    # ------------------------------------------------------------------
    # Admin: approval workflow
    # ------------------------------------------------------------------

    def approve_user(self, target_username: str, approve: bool, approver_nebula_user_id: int,
                      approver_display_name: str) -> Dict:
        target = self.db.get_user_by_username(target_username)
        if not target:
            raise AuthError(f"❌ No Nebula account found with username **{target_username}**.")

        changed = self.db.set_user_approval(
            target['nebula_user_id'], approve, approved_by=approver_nebula_user_id
        )
        if not changed:
            raise AuthError("❌ Could not update approval status. Try again.")

        self.db.log_admin_action(
            approver_nebula_user_id, approver_display_name,
            "approve_user" if approve else "reject_user",
            target['nebula_user_id'], target['display_name'],
            f"target_username={target_username}"
        )

        return {
            'nebula_user_id': target['nebula_user_id'],
            'username': target['username'],
            'approved': approve,
        }

    def list_pending(self, limit: int = 25):
        return self.db.list_pending_users(limit)

    # ------------------------------------------------------------------
    # Admin: add_admin
    # ------------------------------------------------------------------

    def add_admin(self, target_username: str, granter_nebula_user_id: int,
                  granter_display_name: str) -> Dict:
        target = self.db.get_user_by_username(target_username)
        if not target:
            raise AuthError(f"❌ No Nebula account found with username **{target_username}**.")

        self.db.set_user_admin(target['nebula_user_id'], True)
        if not target['is_approved']:
            self.db.set_user_approval(target['nebula_user_id'], True, approved_by=granter_nebula_user_id)

        self.db.log_admin_action(
            granter_nebula_user_id, granter_display_name,
            "add_admin", target['nebula_user_id'], target['display_name'],
            f"target_username={target_username}"
        )

        return {'nebula_user_id': target['nebula_user_id'], 'username': target['username']}
