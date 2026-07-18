from typing import Dict
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
    MESSAGE_COST = 1
    SEARCH_COST = 2
    IMAGE_COST = 5

    def __init__(self, db: DatabaseManager):
        self.db = db

    def check_and_spend(self, nebula_user_id: int, amount: int) -> Dict:
        return self.db.spend_coins(nebula_user_id, amount)

    def get_status(self, nebula_user_id: int) -> Dict:
        return self.db.get_coin_status(nebula_user_id)

    def modify_coins(self, nebula_user_id: int, amount: int, mode: str = "add") -> int:
        return self.db.modify_coins(nebula_user_id, amount, mode)

    def insufficient_funds_message(self, display_name: str, seconds_until_reset: int) -> str:
        return (
            f"⛔ {display_name}, you're out of coins! "
            f"Next reset in approximately **{format_seconds(seconds_until_reset)}**.\n"
            f"You can ask an admin to give you some coins using /add_coin."
        )
