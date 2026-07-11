import os
import re
import bcrypt
from typing import Dict, Optional
from core.database import DatabaseManager


USERNAME_PATTERN = re.compile(r'^[a-zA-Z0-9_]{3,32}$')
MIN_PASSWORD_LENGTH = 8


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
            # Race condition: someone else claimed the username between the
            # check above and the insert. Explicit failure, no retry-guessing.
            raise AuthError(f"❌ Username **{username}** is already taken. Try another.")

        linked = self.db.link_platform_identity(
            platform, platform_user_id, nebula_user_id, platform_display_name
        )
        if not linked:
            # Extremely unlikely given create_user just made a fresh ID, but
            # if it happens, surface it rather than silently proceeding
            # unlinked.
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
        """Attempt to claim the one-time admin bootstrap slot for this new
        user. Returns True if this call successfully made them the first
        admin. Never raises — a wrong or already-used key just means "not
        an admin", the signup itself still succeeds."""
        if not self.bootstrap_api_key:
            # No bootstrap key configured server-side at all.
            return False
        if bootstrap_key != self.bootstrap_api_key:
            return False
        if self.db.is_bootstrap_claimed():
            return False

        won = self.db.try_claim_bootstrap(nebula_user_id)
        if not won:
            # Lost a race to another concurrent signup using the same key.
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
            # Deliberately the same message as "wrong password" below, so
            # login failures don't leak which usernames exist.
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
    # Identity resolution (used by every message-handling path)
    # ------------------------------------------------------------------

    def resolve_identity(self, platform: str, platform_user_id: str) -> Optional[Dict]:
        """Look up the Nebula account linked to a platform identity, if
        any. Returns None if this platform identity has never signed up
        or logged in — callers are expected to tell the user to run
        /signup or /login in that case rather than silently proceeding."""
        return self.db.get_nebula_user_for_platform_identity(platform, platform_user_id)

    def require_approved_identity(self, platform: str, platform_user_id: str) -> Dict:
        """Like resolve_identity, but raises AuthError with a specific,
        user-facing reason for every way this can fail: no account linked,
        or account linked but not yet approved. Use this at the top of any
        AI-handling or tool-using flow."""
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
        """Approve or reject a pending user by username. Rejection is
        implemented as leaving is_approved=0 permanently rather than
        deleting the account, so a rejected user gets a clear "pending"
        message forever rather than being able to re-signup under the
        same username and retry silently. Raises AuthError if the
        username doesn't exist."""
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
        """Promote an existing (approved) Nebula account to admin. Raises
        AuthError if the username doesn't exist. Deliberately does NOT
        require the target to already be approved — an admin granting
        admin rights is itself a form of approval; we auto-approve them
        too so we don't end up with an admin account stuck pending."""
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
