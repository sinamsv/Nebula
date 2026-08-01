import sqlite3
import secrets
from datetime import datetime
from typing import List, Dict, Optional


class DatabaseManager:
    """Platform-agnostic database layer for Nebula.

    Schema is organized around `nebula_users` (a Nebula account) rather than
    guild/channel. Platform identities (Discord, Telegram, Web, ...) are
    linked to a nebula_user via `platform_identities`, and everything else —
    memory, coin balance, admin status — hangs off the nebula_user_id.

    This is a deliberate replacement of the old per-guild/per-channel schema:
    old data does not migrate automatically (different primary keys, no
    reliable way to know which historical Discord user should map to which
    new Nebula account without a signup step). Fresh install expected.

    --- Web panel schema addition (chats / chat-scoped memory) ---

    Discord and Telegram both use ONE continuous conversation_history per
    nebula_user_id, unchanged since day one. The web panel introduces
    multiple named chats per account (confirmed with Sina), each with its
    own token cap, which conversation_history needs to represent without
    disturbing the existing Discord/Telegram path in any way.

    Confirmed approach: conversation_history gets a new nullable `chat_id`
    column (FK -> chats.chat_id).
      - chat_id IS NULL  -> the legacy single-thread history used by
        Discord/Telegram. Every existing query that doesn't filter on
        chat_id keeps working exactly as it did before this migration,
        since old rows are untouched and new Discord/Telegram rows are
        inserted the same way as always (add_message() defaults
        chat_id=None).
      - chat_id IS NOT NULL -> scopes a message to one specific web chat.
        Confirmed with Sina: each web chat has its OWN independent
        200k-token cap (NOT pooled with the account's Discord/Telegram
        cap, and NOT pooled with the account's other web chats). This is
        why get_total_tokens() below takes an optional chat_id: passing
        None sums the legacy (chat_id IS NULL) rows only, exactly like
        before; passing a chat_id sums only that chat's rows.

    This nullable-column approach (rather than, say, a separate table for
    web messages) was chosen so every existing Discord/Telegram code path
    -- add_message(), get_conversation_history(), get_total_tokens(),
    reset_conversation() -- keeps working with zero call-site changes
    unless a caller explicitly opts into chat-scoping by passing a
    chat_id. That was the deciding factor given how much of core/ and
    both bot adapters already call these methods positionally.
    """

    def __init__(self, db_path: str = "nebula.db"):
        self.db_path = db_path
        self.init_database()

    def get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def init_database(self):
        conn = self.get_connection()
        cursor = conn.cursor()

        # ------------------------------------------------------------
        # Identity
        # ------------------------------------------------------------

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS nebula_users (
                nebula_user_id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                display_name TEXT NOT NULL,
                is_admin INTEGER NOT NULL DEFAULT 0,
                is_approved INTEGER NOT NULL DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                approved_at DATETIME,
                approved_by INTEGER REFERENCES nebula_users(nebula_user_id),
                role TEXT NOT NULL DEFAULT 'Member',
                unlimited_mode TEXT NOT NULL DEFAULT 'none',
                unlimited_expires_at DATETIME
            )
        ''')

        cursor.execute("PRAGMA table_info(nebula_users)")
        existing_user_columns = {row[1] for row in cursor.fetchall()}
        if 'role' not in existing_user_columns:
            cursor.execute("ALTER TABLE nebula_users ADD COLUMN role TEXT NOT NULL DEFAULT 'Member'")
            print("Migrated nebula_users: added role column")
        if 'unlimited_mode' not in existing_user_columns:
            cursor.execute("ALTER TABLE nebula_users ADD COLUMN unlimited_mode TEXT NOT NULL DEFAULT 'none'")
            print("Migrated nebula_users: added unlimited_mode column")
        if 'unlimited_expires_at' not in existing_user_columns:
            cursor.execute("ALTER TABLE nebula_users ADD COLUMN unlimited_expires_at DATETIME")
            print("Migrated nebula_users: added unlimited_expires_at column")
        if 'welcome_seen' not in existing_user_columns:
            cursor.execute("ALTER TABLE nebula_users ADD COLUMN welcome_seen INTEGER NOT NULL DEFAULT 1")
            print("Migrated nebula_users: added welcome_seen column")

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS platform_identities (
                platform TEXT NOT NULL,
                platform_user_id TEXT NOT NULL,
                nebula_user_id INTEGER NOT NULL REFERENCES nebula_users(nebula_user_id),
                platform_display_name TEXT,
                linked_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (platform, platform_user_id)
            )
        ''')

        # ------------------------------------------------------------
        # Cross-platform account linking (sync codes)
        # ------------------------------------------------------------
        # Supports the /sync (Discord, or now Web) -> /verify (Telegram, or
        # any future consuming platform) flow: an already-approved,
        # already-linked account generates a one-time code on ITS
        # platform, then carries that code to the NEW platform to prove
        # ownership. Web joins Discord as an ISSUING platform only
        # (confirmed with Sina: one-directional, web never consumes a
        # code -- there is no web-side /verify endpoint). Telegram
        # remains the only consuming platform today.
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS platform_sync_codes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nebula_user_id INTEGER NOT NULL REFERENCES nebula_users(nebula_user_id),
                target_platform TEXT NOT NULL,
                code TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                consumed INTEGER NOT NULL DEFAULT 0
            )
        ''')

        # ------------------------------------------------------------
        # Web chats (NEW) -- multiple named conversations per account,
        # web-only. Discord/Telegram never create rows here; their
        # messages stay chat_id-less in conversation_history (see below).
        # ------------------------------------------------------------

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS chats (
                chat_id INTEGER PRIMARY KEY AUTOINCREMENT,
                nebula_user_id INTEGER NOT NULL REFERENCES nebula_users(nebula_user_id),
                title TEXT NOT NULL DEFAULT 'New Chat',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                last_message_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_chats_nebula_user_id
            ON chats(nebula_user_id)
        ''')

        # ------------------------------------------------------------
        # Conversation memory (per Nebula user, not per channel)
        # ------------------------------------------------------------
        # chat_id: nullable FK -> chats.chat_id. NULL = legacy
        # Discord/Telegram single-thread history (unchanged behavior).
        # Non-null = scoped to one web chat. See class docstring above
        # for the full rationale.

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS conversation_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nebula_user_id INTEGER NOT NULL REFERENCES nebula_users(nebula_user_id),
                chat_id INTEGER REFERENCES chats(chat_id),
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                source_platform TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                token_count INTEGER DEFAULT 0
            )
        ''')
        # Migration path for pre-existing databases created before this
        # column existed: ALTER TABLE ADD COLUMN is idempotent-guarded
        # via the pragma check below, since SQLite has no
        # "ADD COLUMN IF NOT EXISTS". Existing rows get chat_id = NULL
        # automatically (SQLite's default for a newly added column with
        # no explicit DEFAULT), which is exactly the "legacy history"
        # meaning we want -- no data migration/backfill needed.
        cursor.execute("PRAGMA table_info(conversation_history)")
        existing_columns = {row[1] for row in cursor.fetchall()}
        if 'chat_id' not in existing_columns:
            cursor.execute('ALTER TABLE conversation_history ADD COLUMN chat_id INTEGER REFERENCES chats(chat_id)')
            print("Migrated conversation_history: added nullable chat_id column")

        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_conversation_history_user_chat
            ON conversation_history(nebula_user_id, chat_id)
        ''')

        # ------------------------------------------------------------
        # Nebula Coin balances (per Nebula user, global — not per guild)
        # ------------------------------------------------------------

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS coin_balances (
                nebula_user_id INTEGER PRIMARY KEY REFERENCES nebula_users(nebula_user_id),
                balance INTEGER NOT NULL DEFAULT 10,
                last_reset DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # ------------------------------------------------------------
        # Role settings
        # ------------------------------------------------------------

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS role_settings (
                role TEXT PRIMARY KEY,
                allowed_models TEXT NOT NULL,
                allowed_tools TEXT NOT NULL,
                daily_limit REAL NOT NULL,
                weekly_limit REAL NOT NULL,
                max_upload_mb INTEGER NOT NULL DEFAULT 128
            )
        ''')

        cursor.execute("PRAGMA table_info(role_settings)")
        existing_role_settings_columns = {row[1] for row in cursor.fetchall()}
        if 'max_upload_mb' not in existing_role_settings_columns:
            cursor.execute("ALTER TABLE role_settings ADD COLUMN max_upload_mb INTEGER NOT NULL DEFAULT 128")
            cursor.execute("UPDATE role_settings SET max_upload_mb = 128 WHERE role = 'Member'")
            cursor.execute("UPDATE role_settings SET max_upload_mb = 256 WHERE role = 'Trusted'")
            cursor.execute("UPDATE role_settings SET max_upload_mb = 512 WHERE role = 'Researcher'")
            cursor.execute("UPDATE role_settings SET max_upload_mb = 512 WHERE role = 'Admin'")
            print("Migrated role_settings: added max_upload_mb column with default values")

        # Seed default role settings
        default_settings = [
            ('Member', '[]', '["search"]', 50.0, 200.0, 128),
            ('Trusted', '[]', '["search"]', 150.0, 600.0, 256),
            ('Researcher', '[]', '["search"]', 500.0, 2000.0, 512),
            ('Admin', '[]', '["search"]', -1.0, -1.0, 512)
        ]
        for r_name, models, tools, daily, weekly, max_up in default_settings:
            cursor.execute('''
                INSERT OR IGNORE INTO role_settings (role, allowed_models, allowed_tools, daily_limit, weekly_limit, max_upload_mb)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (r_name, models, tools, daily, weekly, max_up))

        # ------------------------------------------------------------
        # Models configuration (JSON-backed DB Table)
        # ------------------------------------------------------------

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS models_config (
                model_id TEXT PRIMARY KEY,
                display_name TEXT NOT NULL,
                allowed_roles TEXT NOT NULL
            )
        ''')

        # ------------------------------------------------------------
        # Coin transactions (rolling rate limit transaction log)
        # ------------------------------------------------------------

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS coin_transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nebula_user_id INTEGER NOT NULL REFERENCES nebula_users(nebula_user_id),
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                coin_cost REAL NOT NULL,
                transaction_type TEXT NOT NULL
            )
        ''')

        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_coin_transactions_user_timestamp
            ON coin_transactions(nebula_user_id, timestamp)
        ''')

        # ------------------------------------------------------------
        # Admin actions log
        # ------------------------------------------------------------

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS admin_actions_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                admin_nebula_user_id INTEGER REFERENCES nebula_users(nebula_user_id),
                admin_display_name TEXT NOT NULL,
                action_type TEXT NOT NULL,
                target_nebula_user_id INTEGER,
                target_display_name TEXT,
                details TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # ------------------------------------------------------------
        # Bootstrap API key state (single-use, first-admin claim)
        # ------------------------------------------------------------

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS bootstrap_state (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                claimed INTEGER NOT NULL DEFAULT 0,
                claimed_by INTEGER REFERENCES nebula_users(nebula_user_id),
                claimed_at DATETIME
            )
        ''')
        cursor.execute('''
            INSERT OR IGNORE INTO bootstrap_state (id, claimed) VALUES (1, 0)
        ''')

        # ------------------------------------------------------------
        # OAuth connections (NEW) -- infrastructure only this release,
        # not wired to any tool yet. One row per (nebula_user_id,
        # provider); tokens are ENCRYPTED (not hashed -- unlike
        # password_hash above, these must be recoverable in plaintext
        # to actually call Google's APIs later). Encryption/decryption
        # lives in core/crypto.py, not here -- this table just stores
        # whatever ciphertext it's handed.
        # ------------------------------------------------------------

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS oauth_connections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nebula_user_id INTEGER NOT NULL REFERENCES nebula_users(nebula_user_id),
                provider TEXT NOT NULL,
                access_token TEXT NOT NULL,
                refresh_token TEXT,
                expires_at DATETIME,
                scopes TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(nebula_user_id, provider)
            )
        ''')

        # ------------------------------------------------------------
        # Discord-specific: legacy per-guild server settings (kept as-is,
        # not part of the platform-agnostic core)
        # ------------------------------------------------------------

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS server_settings (
                guild_id TEXT PRIMARY KEY,
                settings JSON,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        conn.commit()
        conn.close()
        print("Database initialized successfully (user-scoped schema, chat-scoped web memory)")

    # ------------------------------------------------------------------
    # Identity: nebula_users
    # ------------------------------------------------------------------

    def create_user(self, username: str, password_hash: str, display_name: str) -> Optional[int]:
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                INSERT INTO nebula_users (username, password_hash, display_name, welcome_seen)
                VALUES (?, ?, ?, 0)
            ''', (username, password_hash, display_name))
            nebula_user_id = cursor.lastrowid

            cursor.execute('''
                INSERT INTO coin_balances (nebula_user_id, balance, last_reset)
                VALUES (?, 10, CURRENT_TIMESTAMP)
            ''', (nebula_user_id,))

            conn.commit()
            return nebula_user_id
        except sqlite3.IntegrityError:
            conn.rollback()
            return None
        finally:
            conn.close()

    def get_user_by_username(self, username: str) -> Optional[Dict]:
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT nebula_user_id, username, password_hash, display_name,
                   is_admin, is_approved, created_at, role, unlimited_mode, unlimited_expires_at, welcome_seen
            FROM nebula_users WHERE username = ?
        ''', (username,))
        row = cursor.fetchone()
        conn.close()
        if not row:
            return None
        return {
            'nebula_user_id': row[0], 'username': row[1], 'password_hash': row[2],
            'display_name': row[3], 'is_admin': bool(row[4]), 'is_approved': bool(row[5]),
            'created_at': row[6], 'role': row[7], 'unlimited_mode': row[8], 'unlimited_expires_at': row[9],
            'welcome_seen': bool(row[10])
        }

    def get_user_by_id(self, nebula_user_id: int) -> Optional[Dict]:
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT nebula_user_id, username, display_name, is_admin, is_approved, created_at, role, unlimited_mode, unlimited_expires_at, welcome_seen
            FROM nebula_users WHERE nebula_user_id = ?
        ''', (nebula_user_id,))
        row = cursor.fetchone()
        conn.close()
        if not row:
            return None
        return {
            'nebula_user_id': row[0], 'username': row[1], 'display_name': row[2],
            'is_admin': bool(row[3]), 'is_approved': bool(row[4]), 'created_at': row[5],
            'role': row[6], 'unlimited_mode': row[7], 'unlimited_expires_at': row[8],
            'welcome_seen': bool(row[9])
        }

    def set_user_approval(self, nebula_user_id: int, approved: bool, approved_by: int) -> bool:
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE nebula_users
            SET is_approved = ?, approved_at = CURRENT_TIMESTAMP, approved_by = ?
            WHERE nebula_user_id = ?
        ''', (1 if approved else 0, approved_by, nebula_user_id))
        conn.commit()
        changed = cursor.rowcount > 0
        conn.close()
        return changed

    def set_user_admin(self, nebula_user_id: int, is_admin: bool = True) -> bool:
        conn = self.get_connection()
        cursor = conn.cursor()
        role = 'Admin' if is_admin else 'Member'
        cursor.execute('''
            UPDATE nebula_users SET is_admin = ?, role = ? WHERE nebula_user_id = ?
        ''', (1 if is_admin else 0, role, nebula_user_id))
        conn.commit()
        changed = cursor.rowcount > 0
        conn.close()
        return changed

    def set_user_role(self, nebula_user_id: int, role: str, unlimited_mode: str = 'none', unlimited_expires_at: Optional[str] = None) -> bool:
        conn = self.get_connection()
        cursor = conn.cursor()
        is_admin = 1 if role == 'Admin' else 0
        cursor.execute('''
            UPDATE nebula_users
            SET role = ?, is_admin = ?, unlimited_mode = ?, unlimited_expires_at = ?
            WHERE nebula_user_id = ?
        ''', (role, is_admin, unlimited_mode, unlimited_expires_at, nebula_user_id))
        conn.commit()
        changed = cursor.rowcount > 0
        conn.close()
        return changed

    def set_user_welcome_seen(self, nebula_user_id: int, welcome_seen: bool = True) -> bool:
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE nebula_users SET welcome_seen = ? WHERE nebula_user_id = ?
        ''', (1 if welcome_seen else 0, nebula_user_id))
        conn.commit()
        changed = cursor.rowcount > 0
        conn.close()
        return changed

    def count_admins(self) -> int:
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM nebula_users WHERE is_admin = 1')
        count = cursor.fetchone()[0]
        conn.close()
        return count

    def get_all_models(self) -> List[Dict]:
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT model_id, display_name, allowed_roles FROM models_config')
        rows = cursor.fetchall()
        conn.close()
        import json
        return [
            {
                'model_id': r[0],
                'display_name': r[1],
                'allowed_roles': json.loads(r[2])
            }
            for r in rows
        ]

    def save_model(self, model_id: str, display_name: str, allowed_roles: List[str]) -> bool:
        conn = self.get_connection()
        cursor = conn.cursor()
        import json
        roles_str = json.dumps(allowed_roles)
        cursor.execute('''
            INSERT INTO models_config (model_id, display_name, allowed_roles)
            VALUES (?, ?, ?)
            ON CONFLICT(model_id) DO UPDATE SET
                display_name = excluded.display_name,
                allowed_roles = excluded.allowed_roles
        ''', (model_id, display_name, roles_str))
        conn.commit()
        changed = cursor.rowcount > 0
        conn.close()
        return changed

    def delete_model(self, model_id: str) -> bool:
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM models_config WHERE model_id = ?', (model_id,))
        conn.commit()
        changed = cursor.rowcount > 0
        conn.close()
        return changed

    def get_role_settings(self, role: str) -> Optional[Dict]:
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT role, allowed_models, allowed_tools, daily_limit, weekly_limit, max_upload_mb
            FROM role_settings WHERE role = ?
        ''', (role,))
        row = cursor.fetchone()
        conn.close()
        if not row:
            return None
        import json
        return {
            'role': row[0],
            'allowed_models': json.loads(row[1]),
            'allowed_tools': json.loads(row[2]),
            'daily_limit': row[3],
            'weekly_limit': row[4],
            'max_upload_mb': row[5]
        }

    def get_all_role_settings(self) -> List[Dict]:
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT role, allowed_models, allowed_tools, daily_limit, weekly_limit, max_upload_mb
            FROM role_settings
        ''')
        rows = cursor.fetchall()
        conn.close()
        import json
        return [
            {
                'role': r[0],
                'allowed_models': json.loads(r[1]),
                'allowed_tools': json.loads(r[2]),
                'daily_limit': r[3],
                'weekly_limit': r[4],
                'max_upload_mb': r[5]
            }
            for r in rows
        ]

    def update_role_settings(self, role: str, allowed_models: List[str], allowed_tools: List[str], daily_limit: float, weekly_limit: float, max_upload_mb: int) -> bool:
        conn = self.get_connection()
        cursor = conn.cursor()
        import json
        models_str = json.dumps(allowed_models)
        tools_str = json.dumps(allowed_tools)
        cursor.execute('''
            UPDATE role_settings
            SET allowed_models = ?, allowed_tools = ?, daily_limit = ?, weekly_limit = ?, max_upload_mb = ?
            WHERE role = ?
        ''', (models_str, tools_str, daily_limit, weekly_limit, max_upload_mb, role))
        conn.commit()
        changed = cursor.rowcount > 0
        conn.close()
        return changed

    def list_pending_users(self, limit: int = 25) -> List[Dict]:
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT nebula_user_id, username, display_name, created_at
            FROM nebula_users
            WHERE is_approved = 0
            ORDER BY nebula_user_id ASC
            LIMIT ?
        ''', (limit,))
        rows = cursor.fetchall()
        conn.close()
        return [
            {'nebula_user_id': r[0], 'username': r[1], 'display_name': r[2], 'created_at': r[3]}
            for r in rows
        ]

    # ------------------------------------------------------------------
    # Admin lookup by platform (used for one-off admin notifications,
    # e.g. AIHandler's misconfiguration notice — see
    # discord_bot/client.py's notify_admins_if_ai_unconfigured() and
    # telegram_bot/client.py's equivalent)
    # ------------------------------------------------------------------

    def list_admin_platform_identities(self, platform: str) -> List[Dict]:
        """Return every admin's platform_user_id + display name for a
        given platform, via a join on nebula_users.is_admin = 1 --
        mirrors list_pending_users() above in shape/style."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT p.platform_user_id, u.display_name, p.platform_display_name
            FROM nebula_users u
            JOIN platform_identities p ON p.nebula_user_id = u.nebula_user_id
            WHERE u.is_admin = 1 AND p.platform = ?
        ''', (platform,))
        rows = cursor.fetchall()
        conn.close()
        return [
            {'platform_user_id': r[0], 'display_name': r[1], 'platform_display_name': r[2]}
            for r in rows
        ]

    # ------------------------------------------------------------------
    # Bootstrap admin claim (single-use API key)
    # ------------------------------------------------------------------

    def try_claim_bootstrap(self, nebula_user_id: int) -> bool:
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE bootstrap_state
            SET claimed = 1, claimed_by = ?, claimed_at = CURRENT_TIMESTAMP
            WHERE id = 1 AND claimed = 0
        ''', (nebula_user_id,))
        conn.commit()
        won = cursor.rowcount > 0
        conn.close()
        return won

    def is_bootstrap_claimed(self) -> bool:
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT claimed FROM bootstrap_state WHERE id = 1')
        row = cursor.fetchone()
        conn.close()
        return bool(row and row[0])

    # ------------------------------------------------------------------
    # Platform identity linking
    # ------------------------------------------------------------------

    def link_platform_identity(self, platform: str, platform_user_id: str,
                                nebula_user_id: int, platform_display_name: str = None) -> bool:
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT nebula_user_id FROM platform_identities
            WHERE platform = ? AND platform_user_id = ?
        ''', (platform, platform_user_id))
        existing = cursor.fetchone()

        if existing and existing[0] != nebula_user_id:
            conn.close()
            return False

        cursor.execute('''
            INSERT INTO platform_identities (platform, platform_user_id, nebula_user_id, platform_display_name)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(platform, platform_user_id) DO UPDATE SET
                nebula_user_id = excluded.nebula_user_id,
                platform_display_name = excluded.platform_display_name
        ''', (platform, platform_user_id, nebula_user_id, platform_display_name))
        conn.commit()
        conn.close()
        return True

    def get_nebula_user_for_platform_identity(self, platform: str, platform_user_id: str) -> Optional[Dict]:
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT u.nebula_user_id, u.username, u.display_name, u.is_admin, u.is_approved, u.role, u.unlimited_mode, u.unlimited_expires_at, u.welcome_seen
            FROM platform_identities p
            JOIN nebula_users u ON u.nebula_user_id = p.nebula_user_id
            WHERE p.platform = ? AND p.platform_user_id = ?
        ''', (platform, platform_user_id))
        row = cursor.fetchone()
        conn.close()
        if not row:
            return None
        return {
            'nebula_user_id': row[0], 'username': row[1], 'display_name': row[2],
            'is_admin': bool(row[3]), 'is_approved': bool(row[4]),
            'role': row[5], 'unlimited_mode': row[6], 'unlimited_expires_at': row[7],
            'welcome_seen': bool(row[8])
        }

    # ------------------------------------------------------------------
    # Cross-platform account linking (sync codes)
    # ------------------------------------------------------------------

    def create_sync_code(self, nebula_user_id: int, target_platform: str, code: str):
        """Store a new sync code. Any prior UNCONSUMED code for this
        exact (nebula_user_id, target_platform) pair is invalidated first (marked
        consumed), so at most one code is ever "live" at a time — a user
        who runs /sync twice by mistake doesn't end up wondering which of
        two codes is the current one; only the newest is valid."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE platform_sync_codes SET consumed = 1
            WHERE nebula_user_id = ? AND target_platform = ? AND consumed = 0
        ''', (nebula_user_id, target_platform))
        cursor.execute('''
            INSERT INTO platform_sync_codes (nebula_user_id, target_platform, code)
            VALUES (?, ?, ?)
        ''', (nebula_user_id, target_platform, code))
        conn.commit()
        conn.close()

    def get_valid_sync_code(self, nebula_user_id: int, target_platform: str,
                             expiry_minutes: int) -> Optional[Dict]:
        """Return the most recent unconsumed sync code for this
        (nebula_user_id, target_platform) pair, or None if there isn't
        one or it has expired."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, code, created_at FROM platform_sync_codes
            WHERE nebula_user_id = ? AND target_platform = ? AND consumed = 0
            ORDER BY id DESC LIMIT 1
        ''', (nebula_user_id, target_platform))
        row = cursor.fetchone()
        conn.close()
        if not row:
            return None

        sync_id, code, created_at = row
        if isinstance(created_at, str):
            try:
                created_dt = datetime.strptime(created_at, '%Y-%m-%d %H:%M:%S')
            except ValueError:
                created_dt = datetime.strptime(created_at, '%Y-%m-%d %H:%M:%S.%f')
        else:
            created_dt = created_at

        elapsed = datetime.utcnow() - created_dt
        if elapsed.total_seconds() > expiry_minutes * 60:
            return None

        return {'id': sync_id, 'code': code, 'created_at': created_at}

    def consume_sync_code(self, sync_code_id: int):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('UPDATE platform_sync_codes SET consumed = 1 WHERE id = ?', (sync_code_id,))
        conn.commit()
        conn.close()

    # ------------------------------------------------------------------
    # Web chats (NEW)
    # ------------------------------------------------------------------

    def create_chat(self, nebula_user_id: int, title: str = "New Chat") -> int:
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO chats (nebula_user_id, title) VALUES (?, ?)
        ''', (nebula_user_id, title))
        chat_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return chat_id

    def get_chat(self, chat_id: int) -> Optional[Dict]:
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT chat_id, nebula_user_id, title, created_at, last_message_at
            FROM chats WHERE chat_id = ?
        ''', (chat_id,))
        row = cursor.fetchone()
        conn.close()
        if not row:
            return None
        return {
            'chat_id': row[0], 'nebula_user_id': row[1], 'title': row[2],
            'created_at': row[3], 'last_message_at': row[4]
        }

    def list_chats(self, nebula_user_id: int) -> List[Dict]:
        """Ordered by most recently active first, matching what a chat
        sidebar UI wants (most relevant conversations on top)."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT chat_id, nebula_user_id, title, created_at, last_message_at
            FROM chats WHERE nebula_user_id = ?
            ORDER BY last_message_at DESC
        ''', (nebula_user_id,))
        rows = cursor.fetchall()
        conn.close()
        return [
            {'chat_id': r[0], 'nebula_user_id': r[1], 'title': r[2],
             'created_at': r[3], 'last_message_at': r[4]}
            for r in rows
        ]

    def rename_chat(self, chat_id: int, title: str) -> bool:
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('UPDATE chats SET title = ? WHERE chat_id = ?', (title, chat_id))
        conn.commit()
        changed = cursor.rowcount > 0
        conn.close()
        return changed

    def touch_chat(self, chat_id: int):
        """Bump last_message_at to now -- called whenever a message is
        added to a chat, so list_chats()'s ORDER BY reflects actual
        recent activity."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('UPDATE chats SET last_message_at = CURRENT_TIMESTAMP WHERE chat_id = ?', (chat_id,))
        conn.commit()
        conn.close()

    def delete_chat(self, chat_id: int):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM conversation_history WHERE chat_id = ?', (chat_id,))
        cursor.execute('DELETE FROM chats WHERE chat_id = ?', (chat_id,))
        conn.commit()
        conn.close()

    # ------------------------------------------------------------------
    # Conversation memory (per nebula_user_id, cross-platform;
    # optionally scoped to a web chat_id)
    # ------------------------------------------------------------------

    def add_message(self, nebula_user_id: int, role: str, content: str,
                     source_platform: str, token_count: int = 0,
                     chat_id: Optional[int] = None):
        """chat_id defaults to None, preserving exact prior behavior for
        every existing Discord/Telegram call site (none of which pass
        chat_id) -- those rows land in the legacy chat_id-IS-NULL
        history exactly as before this migration. Only web call sites
        pass a real chat_id."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO conversation_history
            (nebula_user_id, chat_id, role, content, source_platform, token_count)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (nebula_user_id, chat_id, role, content, source_platform, token_count))
        conn.commit()
        conn.close()
        if chat_id is not None:
            self.touch_chat(chat_id)

    def get_conversation_history(self, nebula_user_id: int, limit: int = 50,
                                  chat_id: Optional[int] = None) -> List[Dict]:
        """chat_id=None (default): legacy behavior, unchanged -- returns
        the account's chat_id-IS-NULL history (Discord/Telegram),
        exactly as every existing caller already expects. Passing a
        real chat_id scopes the query to that one web chat instead."""
        conn = self.get_connection()
        cursor = conn.cursor()
        if chat_id is None:
            cursor.execute('''
                SELECT role, content, source_platform, timestamp, token_count FROM (
                    SELECT id, role, content, source_platform, timestamp, token_count
                    FROM conversation_history
                    WHERE nebula_user_id = ? AND chat_id IS NULL
                    ORDER BY id DESC
                    LIMIT ?
                ) ORDER BY id ASC
            ''', (nebula_user_id, limit))
        else:
            cursor.execute('''
                SELECT role, content, source_platform, timestamp, token_count FROM (
                    SELECT id, role, content, source_platform, timestamp, token_count
                    FROM conversation_history
                    WHERE nebula_user_id = ? AND chat_id = ?
                    ORDER BY id DESC
                    LIMIT ?
                ) ORDER BY id ASC
            ''', (nebula_user_id, chat_id, limit))
        rows = cursor.fetchall()
        conn.close()
        return [
            {'role': r[0], 'content': r[1], 'source_platform': r[2], 'timestamp': r[3], 'token_count': r[4]}
            for r in rows
        ]

    def get_total_tokens(self, nebula_user_id: int, chat_id: Optional[int] = None) -> int:
        """chat_id=None (default): legacy behavior, unchanged -- sums
        only the account's chat_id-IS-NULL rows (Discord/Telegram's
        shared 200k cap). Passing a real chat_id sums only that web
        chat's rows -- each web chat has its OWN independent 200k cap
        (confirmed with Sina), never pooled with the account-wide
        Discord/Telegram total or with other web chats."""
        conn = self.get_connection()
        cursor = conn.cursor()
        if chat_id is None:
            cursor.execute('''
                SELECT SUM(token_count) FROM conversation_history
                WHERE nebula_user_id = ? AND chat_id IS NULL
            ''', (nebula_user_id,))
        else:
            cursor.execute('''
                SELECT SUM(token_count) FROM conversation_history
                WHERE nebula_user_id = ? AND chat_id = ?
            ''', (nebula_user_id, chat_id))
        result = cursor.fetchone()[0]
        conn.close()
        return result if result else 0

    def reset_conversation(self, nebula_user_id: int, chat_id: Optional[int] = None):
        """chat_id=None (default): legacy behavior, unchanged -- clears
        only the account's chat_id-IS-NULL history (what /memory_reset
        on Discord/Telegram has always cleared). Passing a chat_id
        clears only that one web chat's messages, leaving every other
        chat (and the Discord/Telegram history) untouched."""
        conn = self.get_connection()
        cursor = conn.cursor()
        if chat_id is None:
            cursor.execute('DELETE FROM conversation_history WHERE nebula_user_id = ? AND chat_id IS NULL', (nebula_user_id,))
        else:
            cursor.execute('DELETE FROM conversation_history WHERE nebula_user_id = ? AND chat_id = ?', (nebula_user_id, chat_id))
        conn.commit()
        conn.close()
        print(f"Conversation history reset for nebula_user_id {nebula_user_id} (chat_id={chat_id})")

    # ------------------------------------------------------------------
    # Admin actions log
    # ------------------------------------------------------------------

    def log_admin_action(self, admin_nebula_user_id: Optional[int], admin_display_name: str,
                          action_type: str, target_nebula_user_id: int = None,
                          target_display_name: str = None, details: str = None):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO admin_actions_log
            (admin_nebula_user_id, admin_display_name, action_type,
             target_nebula_user_id, target_display_name, details)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (admin_nebula_user_id, admin_display_name, action_type,
              target_nebula_user_id, target_display_name, details))
        conn.commit()
        conn.close()

    def get_admin_logs(self, limit: int = 50) -> List[Dict]:
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT admin_display_name, action_type, target_display_name, details, timestamp
            FROM admin_actions_log
            ORDER BY id DESC
            LIMIT ?
        ''', (limit,))
        rows = cursor.fetchall()
        conn.close()
        return [
            {'admin_name': r[0], 'action_type': r[1], 'target_name': r[2], 'details': r[3], 'timestamp': r[4]}
            for r in rows
        ]

    # ------------------------------------------------------------------
    # Nebula Coin system (per nebula_user_id, global across platforms)
    # ------------------------------------------------------------------

    DEFAULT_COIN_BALANCE = 10

    def _get_or_create_balance_row(self, cursor, nebula_user_id: int):
        cursor.execute('''
            SELECT balance, last_reset FROM coin_balances WHERE nebula_user_id = ?
        ''', (nebula_user_id,))
        row = cursor.fetchone()
        if row is None:
            cursor.execute('''
                INSERT INTO coin_balances (nebula_user_id, balance, last_reset)
                VALUES (?, ?, CURRENT_TIMESTAMP)
            ''', (nebula_user_id, self.DEFAULT_COIN_BALANCE))
            return self.DEFAULT_COIN_BALANCE, datetime.utcnow()
        balance, last_reset = row
        return balance, last_reset

    def _maybe_reset(self, cursor, nebula_user_id: int, balance: int, last_reset):
        if isinstance(last_reset, str):
            try:
                last_reset_dt = datetime.strptime(last_reset, '%Y-%m-%d %H:%M:%S')
            except ValueError:
                last_reset_dt = datetime.strptime(last_reset, '%Y-%m-%d %H:%M:%S.%f')
        else:
            last_reset_dt = last_reset

        elapsed = datetime.utcnow() - last_reset_dt
        if elapsed.total_seconds() >= 8 * 3600:
            cursor.execute('''
                UPDATE coin_balances SET balance = ?, last_reset = CURRENT_TIMESTAMP
                WHERE nebula_user_id = ?
            ''', (self.DEFAULT_COIN_BALANCE, nebula_user_id))
            return self.DEFAULT_COIN_BALANCE, datetime.utcnow()
        return balance, last_reset_dt

    def get_coin_status(self, nebula_user_id: int) -> Dict:
        conn = self.get_connection()
        cursor = conn.cursor()
        balance, last_reset = self._get_or_create_balance_row(cursor, nebula_user_id)
        balance, last_reset_dt = self._maybe_reset(cursor, nebula_user_id, balance, last_reset)
        conn.commit()
        seconds_until_reset = max(0, int(8 * 3600 - (datetime.utcnow() - last_reset_dt).total_seconds()))
        conn.close()
        return {'balance': balance, 'seconds_until_reset': seconds_until_reset}

    def spend_coins(self, nebula_user_id: int, amount: int) -> Dict:
        conn = self.get_connection()
        cursor = conn.cursor()
        balance, last_reset = self._get_or_create_balance_row(cursor, nebula_user_id)
        balance, last_reset_dt = self._maybe_reset(cursor, nebula_user_id, balance, last_reset)
        seconds_until_reset = max(0, int(8 * 3600 - (datetime.utcnow() - last_reset_dt).total_seconds()))

        if balance < amount or balance <= 0:
            conn.commit()
            conn.close()
            return {'success': False, 'balance': balance, 'seconds_until_reset': seconds_until_reset}

        new_balance = balance - amount
        cursor.execute('''
            UPDATE coin_balances SET balance = ? WHERE nebula_user_id = ?
        ''', (new_balance, nebula_user_id))
        conn.commit()
        conn.close()
        return {'success': True, 'balance': new_balance, 'seconds_until_reset': seconds_until_reset}

    def modify_coins(self, nebula_user_id: int, amount: int, mode: str = "add") -> int:
        conn = self.get_connection()
        cursor = conn.cursor()
        balance, _ = self._get_or_create_balance_row(cursor, nebula_user_id)
        new_balance = amount if mode == "set" else balance + amount
        cursor.execute('''
            UPDATE coin_balances SET balance = ? WHERE nebula_user_id = ?
        ''', (new_balance, nebula_user_id))
        conn.commit()
        conn.close()
        return new_balance

    # ------------------------------------------------------------------
    # OAuth connections (NEW) -- infrastructure only, not wired to any
    # tool this release. Tokens are stored encrypted (ciphertext in,
    # ciphertext out) -- see core/crypto.py for the encrypt/decrypt
    # helpers. This layer never sees plaintext.
    # ------------------------------------------------------------------

    def upsert_oauth_connection(self, nebula_user_id: int, provider: str,
                                 access_token_encrypted: str,
                                 refresh_token_encrypted: Optional[str],
                                 expires_at: Optional[str], scopes: Optional[str]) -> None:
        """One row per (nebula_user_id, provider) -- re-running the OAuth
        flow for a provider a user already connected updates the
        existing row (fresh tokens, possibly fresh scopes) rather than
        creating a duplicate, matching how Google's own re-consent flow
        expects to be handled."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO oauth_connections
                (nebula_user_id, provider, access_token, refresh_token, expires_at, scopes, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(nebula_user_id, provider) DO UPDATE SET
                access_token = excluded.access_token,
                refresh_token = COALESCE(excluded.refresh_token, oauth_connections.refresh_token),
                expires_at = excluded.expires_at,
                scopes = excluded.scopes,
                updated_at = CURRENT_TIMESTAMP
        ''', (nebula_user_id, provider, access_token_encrypted, refresh_token_encrypted, expires_at, scopes))
        conn.commit()
        conn.close()

    def get_oauth_connection(self, nebula_user_id: int, provider: str) -> Optional[Dict]:
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT nebula_user_id, provider, access_token, refresh_token, expires_at, scopes, created_at, updated_at
            FROM oauth_connections WHERE nebula_user_id = ? AND provider = ?
        ''', (nebula_user_id, provider))
        row = cursor.fetchone()
        conn.close()
        if not row:
            return None
        return {
            'nebula_user_id': row[0], 'provider': row[1], 'access_token': row[2],
            'refresh_token': row[3], 'expires_at': row[4], 'scopes': row[5],
            'created_at': row[6], 'updated_at': row[7],
        }
