import sqlite3
import secrets
from datetime import datetime
from typing import List, Dict, Optional


class DatabaseManager:
    """Platform-agnostic database layer for Nebula.

    Schema is organized around `nebula_users` (a Nebula account) rather than
    guild/channel. Platform identities (Discord, Telegram, ...) are linked to
    a nebula_user via `platform_identities`, and everything else — memory,
    coin balance, admin status — hangs off the nebula_user_id.

    This is a deliberate replacement of the old per-guild/per-channel schema:
    old data does not migrate automatically (different primary keys, no
    reliable way to know which historical Discord user should map to which
    new Nebula account without a signup step). Fresh install expected.
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

        # A Nebula account. This is the thing memory, coins, and admin
        # status actually belong to — platforms are just doors into it.
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
                approved_by INTEGER REFERENCES nebula_users(nebula_user_id)
            )
        ''')

        # Links a platform-specific identity (Discord user ID, Telegram user
        # ID, ...) to a Nebula account. One Nebula account can have many
        # platform identities; a platform identity maps to exactly one
        # Nebula account.
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
        # Conversation memory (per Nebula user, not per channel)
        # ------------------------------------------------------------

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS conversation_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nebula_user_id INTEGER NOT NULL REFERENCES nebula_users(nebula_user_id),
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                source_platform TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                token_count INTEGER DEFAULT 0
            )
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
        print("Database initialized successfully (user-scoped schema)")

    # ------------------------------------------------------------------
    # Identity: nebula_users
    # ------------------------------------------------------------------

    def create_user(self, username: str, password_hash: str, display_name: str) -> Optional[int]:
        """Create a new Nebula account. Returns the new nebula_user_id, or
        None if the username is already taken."""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                INSERT INTO nebula_users (username, password_hash, display_name)
                VALUES (?, ?, ?)
            ''', (username, password_hash, display_name))
            nebula_user_id = cursor.lastrowid

            # Every new user gets a coin balance row up front so downstream
            # coin logic never has to special-case "row doesn't exist yet".
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
                   is_admin, is_approved, created_at
            FROM nebula_users WHERE username = ?
        ''', (username,))
        row = cursor.fetchone()
        conn.close()
        if not row:
            return None
        return {
            'nebula_user_id': row[0], 'username': row[1], 'password_hash': row[2],
            'display_name': row[3], 'is_admin': bool(row[4]), 'is_approved': bool(row[5]),
            'created_at': row[6]
        }

    def get_user_by_id(self, nebula_user_id: int) -> Optional[Dict]:
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT nebula_user_id, username, display_name, is_admin, is_approved, created_at
            FROM nebula_users WHERE nebula_user_id = ?
        ''', (nebula_user_id,))
        row = cursor.fetchone()
        conn.close()
        if not row:
            return None
        return {
            'nebula_user_id': row[0], 'username': row[1], 'display_name': row[2],
            'is_admin': bool(row[3]), 'is_approved': bool(row[4]), 'created_at': row[5]
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
        cursor.execute('''
            UPDATE nebula_users SET is_admin = ? WHERE nebula_user_id = ?
        ''', (1 if is_admin else 0, nebula_user_id))
        conn.commit()
        changed = cursor.rowcount > 0
        conn.close()
        return changed

    def list_pending_users(self, limit: int = 25) -> List[Dict]:
        """Users who signed up but are not yet approved (nor rejected-and-
        left pending forever — rejection is just leaving is_approved=0).
        Ordered by nebula_user_id rather than created_at for the same
        reason as get_conversation_history: CURRENT_TIMESTAMP's
        second-level precision can tie for near-simultaneous signups."""
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
    # Bootstrap admin claim (single-use API key)
    # ------------------------------------------------------------------

    def try_claim_bootstrap(self, nebula_user_id: int) -> bool:
        """Atomically claim the one-time bootstrap slot. Returns True if
        this call was the one that claimed it, False if it was already
        claimed by someone else. Callers must independently verify the
        API key matches before calling this — this only enforces
        single-use, not correctness of the key."""
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
        """Link a platform identity to a Nebula account. Fails (returns
        False) if that exact platform identity is already linked to a
        DIFFERENT Nebula account — one Discord ID can't belong to two
        Nebula accounts. Re-linking to the SAME account (e.g. re-login)
        is idempotent and succeeds."""
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
            SELECT u.nebula_user_id, u.username, u.display_name, u.is_admin, u.is_approved
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
            'is_admin': bool(row[3]), 'is_approved': bool(row[4])
        }

    # ------------------------------------------------------------------
    # Conversation memory (per nebula_user_id, cross-platform)
    # ------------------------------------------------------------------

    def add_message(self, nebula_user_id: int, role: str, content: str,
                     source_platform: str, token_count: int = 0):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO conversation_history
            (nebula_user_id, role, content, source_platform, token_count)
            VALUES (?, ?, ?, ?, ?)
        ''', (nebula_user_id, role, content, source_platform, token_count))
        conn.commit()
        conn.close()

    def get_conversation_history(self, nebula_user_id: int, limit: int = 50) -> List[Dict]:
        # Ordered by `id`, not `timestamp`: CURRENT_TIMESTAMP has only
        # second-level precision in SQLite, so multiple messages inserted
        # within the same second (very plausible here — an assistant
        # reply followed immediately by the next user message, or two
        # platforms both writing around the same moment) can get an
        # identical timestamp, making ORDER BY timestamp non-deterministic
        # for ties. `id` is AUTOINCREMENT and strictly monotonic, so it's
        # the reliable ordering key. The inner query grabs the most recent
        # `limit` rows by id descending, then the outer query re-sorts
        # those to ascending (chronological) order for the caller.
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT role, content, source_platform, timestamp, token_count FROM (
                SELECT id, role, content, source_platform, timestamp, token_count
                FROM conversation_history
                WHERE nebula_user_id = ?
                ORDER BY id DESC
                LIMIT ?
            ) ORDER BY id ASC
        ''', (nebula_user_id, limit))
        rows = cursor.fetchall()
        conn.close()
        return [
            {'role': r[0], 'content': r[1], 'source_platform': r[2], 'timestamp': r[3], 'token_count': r[4]}
            for r in rows
        ]

    def get_total_tokens(self, nebula_user_id: int) -> int:
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT SUM(token_count) FROM conversation_history WHERE nebula_user_id = ?
        ''', (nebula_user_id,))
        result = cursor.fetchone()[0]
        conn.close()
        return result if result else 0

    def reset_conversation(self, nebula_user_id: int):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM conversation_history WHERE nebula_user_id = ?', (nebula_user_id,))
        conn.commit()
        conn.close()
        print(f"Conversation history reset for nebula_user_id {nebula_user_id}")

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
        # Ordered by id (not timestamp) for the same reason as
        # get_conversation_history — avoids non-deterministic ordering
        # when multiple admin actions land in the same second.
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
