from typing import Dict, Optional
from datetime import datetime
from core.database import DatabaseManager


def format_seconds(seconds: int) -> str:
    if seconds <= 0:
        return "a few moments"
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    parts = []
    if hours > 0:
        parts.append(f"{hours} hours")
    if minutes > 0 or not parts:
        parts.append(f"{minutes} minutes")
    return " and ".join(parts)


class CoinManager:
    # Costs as exact multipliers/fractions
    INPUT_TOKEN_MULTIPLIER = 0.01  # 1 coin per 100 input tokens
    OUTPUT_TOKEN_MULTIPLIER = 0.05  # 1 coin per 20 output tokens
    MESSAGE_COST = 1.0
    SEARCH_COST = 2.0
    IMAGE_COST = 15.0  # Image generation is 15 coins per image per spec

    def __init__(self, db: DatabaseManager):
        self.db = db

    def get_rolling_usage(self, nebula_user_id: int, window_hours: float) -> float:
        conn = self.db.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT SUM(coin_cost) FROM coin_transactions
            WHERE nebula_user_id = ? AND timestamp >= datetime('now', ?)
        ''', (nebula_user_id, f'-{window_hours} hours'))
        row = cursor.fetchone()
        conn.close()
        return row[0] if row[0] is not None else 0.0

    def get_transactions_in_window(self, nebula_user_id: int, window_hours: float) -> list:
        conn = self.db.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT timestamp, coin_cost FROM coin_transactions
            WHERE nebula_user_id = ? AND timestamp >= datetime('now', ?)
            ORDER BY timestamp ASC
        ''', (nebula_user_id, f'-{window_hours} hours'))
        rows = cursor.fetchall()
        conn.close()
        return rows

    def compute_seconds_until_free(self, nebula_user_id: int, limit: float, current_usage: float, amount: float, window_hours: float) -> int:
        needed = (current_usage + amount) - limit
        if needed <= 0:
            return 0

        txs = self.get_transactions_in_window(nebula_user_id, window_hours)
        running_sum = 0.0
        for timestamp_str, coin_cost in txs:
            if coin_cost <= 0:
                continue
            running_sum += coin_cost
            if running_sum >= needed:
                try:
                    from datetime import datetime
                    try:
                        tx_time = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')
                    except ValueError:
                        tx_time = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S.%f')

                    import calendar
                    tx_epoch = calendar.timegm(tx_time.utctimetuple())
                    current_epoch = calendar.timegm(datetime.utcnow().utctimetuple())

                    elapsed = current_epoch - tx_epoch
                    window_seconds = int(window_hours * 3600)
                    remaining = window_seconds - elapsed
                    return max(1, remaining)
                except Exception:
                    break
        return int(window_hours * 3600)

    def get_user_role_and_limits(self, nebula_user_id: int) -> dict:
        user = self.db.get_user_by_id(nebula_user_id)
        if not user:
            return {
                'role': 'Member',
                'unlimited_mode': 'none',
                'unlimited_expires_at': None,
                'daily_limit': 50.0,
                'weekly_limit': 200.0
            }
        role = user.get('role', 'Member')
        settings = self.db.get_role_settings(role)
        if not settings:
            defaults = {
                'Member': (50.0, 200.0),
                'Trusted': (150.0, 600.0),
                'Researcher': (500.0, 2000.0),
                'Admin': (-1.0, -1.0)
            }
            dl, wl = defaults.get(role, (50.0, 200.0))
            settings = {'daily_limit': dl, 'weekly_limit': wl}

        return {
            'role': role,
            'unlimited_mode': user.get('unlimited_mode', 'none'),
            'unlimited_expires_at': user.get('unlimited_expires_at'),
            'daily_limit': settings['daily_limit'],
            'weekly_limit': settings['weekly_limit']
        }

    def is_unlimited_active(self, role: str, unlimited_mode: str, unlimited_expires_at) -> bool:
        if role == 'Admin':
            return True
        if role == 'Researcher':
            if unlimited_mode == 'permanent':
                return True
            if unlimited_mode == 'temporary' and unlimited_expires_at:
                try:
                    from datetime import datetime
                    if isinstance(unlimited_expires_at, str):
                        try:
                            expires_dt = datetime.strptime(unlimited_expires_at, '%Y-%m-%d %H:%M:%S')
                        except ValueError:
                            expires_dt = datetime.strptime(unlimited_expires_at, '%Y-%m-%d %H:%M:%S.%f')
                    else:
                        expires_dt = unlimited_expires_at

                    return datetime.utcnow() < expires_dt
                except Exception:
                    return False
        return False

    def check_and_spend(self, nebula_user_id: int, amount: float, transaction_type: str = 'message') -> Dict:
        info = self.get_user_role_and_limits(nebula_user_id)
        role = info['role']
        daily_limit = info['daily_limit']
        weekly_limit = info['weekly_limit']

        unlimited = self.is_unlimited_active(role, info['unlimited_mode'], info['unlimited_expires_at'])

        daily_usage = self.get_rolling_usage(nebula_user_id, 24.0)
        weekly_usage = self.get_rolling_usage(nebula_user_id, 168.0)

        if role == 'Admin' or unlimited:
            self.log_transaction(nebula_user_id, amount, transaction_type)
            return {
                'success': True,
                'daily_usage': daily_usage,
                'weekly_usage': weekly_usage,
                'seconds_until_reset': 0
            }

        if daily_limit >= 0 and (daily_usage + amount) > daily_limit:
            seconds_until_reset = self.compute_seconds_until_free(nebula_user_id, daily_limit, daily_usage, amount, 24.0)
            return {
                'success': False,
                'daily_usage': daily_usage,
                'weekly_usage': weekly_usage,
                'seconds_until_reset': seconds_until_reset,
                'blocked_by': 'daily'
            }

        if weekly_limit >= 0 and (weekly_usage + amount) > weekly_limit:
            seconds_until_reset = self.compute_seconds_until_free(nebula_user_id, weekly_limit, weekly_usage, amount, 168.0)
            return {
                'success': False,
                'daily_usage': daily_usage,
                'weekly_usage': weekly_usage,
                'seconds_until_reset': seconds_until_reset,
                'blocked_by': 'weekly'
            }

        self.log_transaction(nebula_user_id, amount, transaction_type)
        return {
            'success': True,
            'daily_usage': daily_usage + amount,
            'weekly_usage': weekly_usage + amount,
            'seconds_until_reset': 0
        }

    def log_transaction(self, nebula_user_id: int, coin_cost: float, transaction_type: str):
        conn = self.db.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO coin_transactions (nebula_user_id, coin_cost, transaction_type, timestamp)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
        ''', (nebula_user_id, coin_cost, transaction_type))
        conn.commit()
        conn.close()

    def get_status(self, nebula_user_id: int) -> Dict:
        info = self.get_user_role_and_limits(nebula_user_id)
        role = info['role']
        daily_limit = info['daily_limit']
        weekly_limit = info['weekly_limit']
        unlimited = self.is_unlimited_active(role, info['unlimited_mode'], info['unlimited_expires_at'])

        daily_usage = self.get_rolling_usage(nebula_user_id, 24.0)
        weekly_usage = self.get_rolling_usage(nebula_user_id, 168.0)

        if role == 'Admin' or unlimited:
            return {
                'balance': 9999,
                'seconds_until_reset': 0,
                'daily_limit': daily_limit,
                'weekly_limit': weekly_limit,
                'daily_usage': daily_usage,
                'weekly_usage': weekly_usage,
                'role': role,
                'unlimited_mode': info['unlimited_mode'],
                'unlimited_expires_at': str(info['unlimited_expires_at']) if info['unlimited_expires_at'] else None
            }

        remaining_daily = max(0.0, daily_limit - daily_usage)
        seconds_until_reset = 0
        if remaining_daily <= 0:
            seconds_until_reset = self.compute_seconds_until_free(nebula_user_id, daily_limit, daily_usage, 1.0, 24.0)

        return {
            'balance': int(remaining_daily),
            'seconds_until_reset': seconds_until_reset,
            'daily_limit': daily_limit,
            'weekly_limit': weekly_limit,
            'daily_usage': daily_usage,
            'weekly_usage': weekly_usage,
            'role': role,
            'unlimited_mode': info['unlimited_mode'],
            'unlimited_expires_at': str(info['unlimited_expires_at']) if info['unlimited_expires_at'] else None
        }

    def modify_coins(self, nebula_user_id: int, amount: float, mode: str = "add") -> float:
        info = self.get_user_role_and_limits(nebula_user_id)
        daily_limit = info['daily_limit']
        daily_usage = self.get_rolling_usage(nebula_user_id, 24.0)

        if mode == "add":
            self.log_transaction(nebula_user_id, -amount, 'admin_adjustment')
            new_usage = max(0.0, daily_usage - amount)
        else:  # "set"
            if daily_limit >= 0:
                adjustment = (daily_limit - amount) - daily_usage
                self.log_transaction(nebula_user_id, adjustment, 'admin_adjustment')
                new_usage = max(0.0, daily_limit - amount)
            else:
                self.log_transaction(nebula_user_id, -amount, 'admin_adjustment')
                new_usage = 0.0

        remaining = max(0.0, daily_limit - new_usage) if daily_limit >= 0 else 9999.0
        return int(remaining)

    def insufficient_funds_message(self, display_name: str, seconds_until_reset: int) -> str:
        return (
            f"⛔ {display_name}, you've hit your coin rate limit! "
            f"More usage will free up in approximately **{format_seconds(seconds_until_reset)}**."
        )
