import sqlite3
import json
from datetime import datetime
from typing import List, Dict, Optional
import os

class DatabaseManager:
    """Manages SQLite database operations for Nebula bot."""

    def __init__(self, db_path: str = "nebula.db"):
        """Initialize database connection."""
        self.db_path = db_path
        self.init_database()

    def get_connection(self):
        """Get a database connection."""
        return sqlite3.connect(self.db_path)

    def init_database(self):
        """Initialize database tables."""
        conn = self.get_connection()
        cursor = conn.cursor()

        # Conversation history table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS conversation_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id TEXT NOT NULL,
                channel_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                display_name TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                token_count INTEGER DEFAULT 0
            )
        ''')

        # User profiles table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_profiles (
                user_id TEXT PRIMARY KEY,
                display_name TEXT NOT NULL,
                guild_id TEXT NOT NULL,
                first_seen DATETIME DEFAULT CURRENT_TIMESTAMP,
                last_seen DATETIME DEFAULT CURRENT_TIMESTAMP,
                message_count INTEGER DEFAULT 0
            )
        ''')

        # Server settings table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS server_settings (
                guild_id TEXT PRIMARY KEY,
                settings JSON,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Admin actions log table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS admin_actions_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id TEXT NOT NULL,
                admin_id TEXT NOT NULL,
                admin_name TEXT NOT NULL,
                action_type TEXT NOT NULL,
                target_id TEXT,
                target_name TEXT,
                details TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Nebula Coin balances table (per user, per guild)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS coin_balances (
                user_id TEXT NOT NULL,
                guild_id TEXT NOT NULL,
                balance INTEGER NOT NULL DEFAULT 10,
                last_reset DATETIME DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (user_id, guild_id)
            )
        ''')

        conn.commit()
        conn.close()
        print("Database initialized successfully")

    def add_message(self, guild_id: str, channel_id: str, user_id: str,
                   display_name: str, role: str, content: str, token_count: int = 0):
        """Add a message to conversation history."""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO conversation_history
            (guild_id, channel_id, user_id, display_name, role, content, token_count)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (guild_id, channel_id, user_id, display_name, role, content, token_count))

        conn.commit()
        conn.close()

    def get_conversation_history(self, guild_id: str, channel_id: str,
                                limit: int = 50) -> List[Dict]:
        """Retrieve recent conversation history."""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT display_name, role, content, timestamp, token_count
            FROM conversation_history
            WHERE guild_id = ? AND channel_id = ?
            ORDER BY timestamp DESC
            LIMIT ?
        ''', (guild_id, channel_id, limit))

        messages = []
        for row in cursor.fetchall():
            messages.append({
                'display_name': row[0],
                'role': row[1],
                'content': row[2],
                'timestamp': row[3],
                'token_count': row[4]
            })

        conn.close()
        return list(reversed(messages))  # Return in chronological order

    def get_total_tokens(self, guild_id: str, channel_id: str) -> int:
        """Get total token count for a conversation."""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT SUM(token_count)
            FROM conversation_history
            WHERE guild_id = ? AND channel_id = ?
        ''', (guild_id, channel_id))

        result = cursor.fetchone()[0]
        conn.close()
        return result if result else 0

    def reset_conversation(self, guild_id: str, channel_id: str):
        """Reset conversation history for a channel."""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            DELETE FROM conversation_history
            WHERE guild_id = ? AND channel_id = ?
        ''', (guild_id, channel_id))

        conn.commit()
        conn.close()
        print(f"Conversation history reset for guild {guild_id}, channel {channel_id}")

    def update_user_profile(self, user_id: str, display_name: str, guild_id: str):
        """Update or create user profile."""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO user_profiles (user_id, display_name, guild_id, message_count)
            VALUES (?, ?, ?, 1)
            ON CONFLICT(user_id) DO UPDATE SET
                display_name = excluded.display_name,
                last_seen = CURRENT_TIMESTAMP,
                message_count = message_count + 1
        ''', (user_id, display_name, guild_id))

        conn.commit()
        conn.close()

    def get_user_activity(self, user_id: str, guild_id: str) -> Optional[Dict]:
        """Get user activity information."""
        conn = self.get_connection()
        cursor = conn.cursor()

        # Get user profile
        cursor.execute('''
            SELECT display_name, first_seen, last_seen, message_count
            FROM user_profiles
            WHERE user_id = ? AND guild_id = ?
        ''', (user_id, guild_id))

        profile = cursor.fetchone()
        if not profile:
            conn.close()
            return None

        # Get recent message count
        cursor.execute('''
            SELECT COUNT(*)
            FROM conversation_history
            WHERE user_id = ? AND guild_id = ?
            AND timestamp > datetime('now', '-7 days')
        ''', (user_id, guild_id))

        recent_messages = cursor.fetchone()[0]

        conn.close()

        return {
            'display_name': profile[0],
            'first_seen': profile[1],
            'last_seen': profile[2],
            'total_messages': profile[3],
            'messages_last_7_days': recent_messages
        }

    def log_admin_action(self, guild_id: str, admin_id: str, admin_name: str,
                        action_type: str, target_id: str = None,
                        target_name: str = None, details: str = None):
        """Log an admin action."""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO admin_actions_log
            (guild_id, admin_id, admin_name, action_type, target_id, target_name, details)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (guild_id, admin_id, admin_name, action_type, target_id, target_name, details))

        conn.commit()
        conn.close()

    def get_admin_logs(self, guild_id: str, limit: int = 50) -> List[Dict]:
        """Retrieve admin action logs."""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT admin_name, action_type, target_name, details, timestamp
            FROM admin_actions_log
            WHERE guild_id = ?
            ORDER BY timestamp DESC
            LIMIT ?
        ''', (guild_id, limit))

        logs = []
        for row in cursor.fetchall():
            logs.append({
                'admin_name': row[0],
                'action_type': row[1],
                'target_name': row[2],
                'details': row[3],
                'timestamp': row[4]
            })

        conn.close()
        return logs

    # ------------------------------------------------------------------
    # Nebula Coin system
    # ------------------------------------------------------------------

    DEFAULT_COIN_BALANCE = 10

    def _get_or_create_balance_row(self, cursor, user_id: str, guild_id: str):
        """Internal helper: fetch the balance row, creating it if missing.
        Must be called with an already-open cursor (no commit here)."""
        cursor.execute('''
            SELECT balance, last_reset FROM coin_balances
            WHERE user_id = ? AND guild_id = ?
        ''', (user_id, guild_id))
        row = cursor.fetchone()

        if row is None:
            cursor.execute('''
                INSERT INTO coin_balances (user_id, guild_id, balance, last_reset)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            ''', (user_id, guild_id, self.DEFAULT_COIN_BALANCE))
            return self.DEFAULT_COIN_BALANCE, datetime.utcnow()

        balance, last_reset = row
        return balance, last_reset

    def _maybe_reset(self, cursor, user_id: str, guild_id: str, balance: int, last_reset):
        """Internal helper: reset balance to default if 8h have passed since last_reset.
        Returns the (possibly updated) balance and last_reset."""
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
                UPDATE coin_balances
                SET balance = ?, last_reset = CURRENT_TIMESTAMP
                WHERE user_id = ? AND guild_id = ?
            ''', (self.DEFAULT_COIN_BALANCE, user_id, guild_id))
            return self.DEFAULT_COIN_BALANCE, datetime.utcnow()

        return balance, last_reset_dt

    def get_coin_status(self, user_id: str, guild_id: str) -> Dict:
        """Get a user's current coin balance, applying an 8h reset if due.
        Returns dict with 'balance' and 'seconds_until_reset'."""
        conn = self.get_connection()
        cursor = conn.cursor()

        balance, last_reset = self._get_or_create_balance_row(cursor, user_id, guild_id)
        balance, last_reset_dt = self._maybe_reset(cursor, user_id, guild_id, balance, last_reset)

        conn.commit()

        seconds_until_reset = max(0, int(8 * 3600 - (datetime.utcnow() - last_reset_dt).total_seconds()))

        conn.close()
        return {
            'balance': balance,
            'seconds_until_reset': seconds_until_reset
        }

    def spend_coins(self, user_id: str, guild_id: str, amount: int) -> Dict:
        """Attempt to spend `amount` coins. Applies 8h reset first if due.
        Returns dict: {'success': bool, 'balance': int, 'seconds_until_reset': int}
        If balance (after reset check) is <= 0, fails without deducting."""
        conn = self.get_connection()
        cursor = conn.cursor()

        balance, last_reset = self._get_or_create_balance_row(cursor, user_id, guild_id)
        balance, last_reset_dt = self._maybe_reset(cursor, user_id, guild_id, balance, last_reset)

        seconds_until_reset = max(0, int(8 * 3600 - (datetime.utcnow() - last_reset_dt).total_seconds()))

        if balance <= 0:
            conn.commit()
            conn.close()
            return {'success': False, 'balance': balance, 'seconds_until_reset': seconds_until_reset}

        new_balance = balance - amount
        cursor.execute('''
            UPDATE coin_balances
            SET balance = ?
            WHERE user_id = ? AND guild_id = ?
        ''', (new_balance, user_id, guild_id))

        conn.commit()
        conn.close()

        return {'success': True, 'balance': new_balance, 'seconds_until_reset': seconds_until_reset}

    def modify_coins(self, user_id: str, guild_id: str, amount: int, mode: str = "add") -> int:
        """Admin operation: add to or set a user's coin balance.
        mode: 'add' -> balance += amount ; 'set' -> balance = amount
        Does NOT trigger or interact with the 8h reset timer or cap at 10 —
        admins may intentionally grant more than the default amount.
        Returns the new balance."""
        conn = self.get_connection()
        cursor = conn.cursor()

        balance, last_reset = self._get_or_create_balance_row(cursor, user_id, guild_id)

        if mode == "set":
            new_balance = amount
        else:
            new_balance = balance + amount

        cursor.execute('''
            UPDATE coin_balances
            SET balance = ?
            WHERE user_id = ? AND guild_id = ?
        ''', (new_balance, user_id, guild_id))

        conn.commit()
        conn.close()

        return new_balance
