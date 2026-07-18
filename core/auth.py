import os
import re
import secrets
import bcrypt
from typing import Dict, Optional
from core.database import DatabaseManager


USERNAME_PATTERN = re.compile(r'^[a-zA-Z0-9_]{3,32}$')
MIN_PASSWORD_LENGTH = 8

SYNC_CODE_LENGTH = 6
SYNC_CODE_EXPIRY_MINUTES = 10


class AuthError(Exception):
    pass


class AuthManager:
    def __init__(self, db: DatabaseManager):
        self.db = db
        self.bootstrap_api_key = os.getenv('ADMIN_BOOTSTRAP_KEY')

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

    def signup(self, username: str, password: str, display_name: str,
               platform: str, platform_user_id: str,
               platform_display_name: str = None,
               bootstrap_key: Optional[str] = None) -> Dict:
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

    def generate_sync_code(self, nebula_user_id: int, target_platform: str) -> str:
        code = f"{secrets.randbelow(10 ** SYNC_CODE_LENGTH):0{SYNC_CODE_LENGTH}d}"
        self.db.create_sync_code(nebula_user_id, target_platform, code)
        return code

    def verify_sync_code(self, username: str, code: str, target_platform: str,
                          platform_user_id: str, platform_display_name: str = None) -> Dict:
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

        self.db.consume_sync_code(pending['id'])

        return {
            'nebula_user_id': target['nebula_user_id'],
            'username': target['username'],
            'is_approved': target['is_approved'],
            'is_admin': target['is_admin'],
        }

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

    def approve_user_by_id(self, target_nebula_user_id: int, approve: bool,
                            approver_nebula_user_id: int, approver_display_name: str) -> Dict:
        """Id-based variant of approve_user(), added for web_backend's
        POST /admin/users/{id}/review (confirmed shape: path takes an
        id, not a username). Discord/Telegram's /approve_user command
        keeps using the username-based approve_user() above unchanged
        -- this is purely additive, not a replacement, since a Discord
        slash command naturally has the target's username on hand (an
        admin can't easily paste a nebula_user_id) while a web
        pending-users list naturally has the row's id on hand.
        Delegates to the same DB calls as approve_user() to avoid
        duplicating the approval logic itself."""
        target = self.db.get_user_by_id(target_nebula_user_id)
        if not target:
            raise AuthError(f"❌ No Nebula account found with id **{target_nebula_user_id}**.")

        changed = self.db.set_user_approval(
            target['nebula_user_id'], approve, approved_by=approver_nebula_user_id
        )
        if not changed:
            raise AuthError("❌ Could not update approval status. Try again.")

        self.db.log_admin_action(
            approver_nebula_user_id, approver_display_name,
            "approve_user" if approve else "reject_user",
            target['nebula_user_id'], target['display_name'],
            f"target_username={target['username']}"
        )

        return {
            'nebula_user_id': target['nebula_user_id'],
            'username': target['username'],
            'approved': approve,
        }

    def list_pending(self, limit: int = 25):
        return self.db.list_pending_users(limit)

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
