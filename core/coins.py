"""Platform-agnostic Nebula Coin rate-limiting system.

Previously this logic lived entirely inside discord_bot/coin_commands.py
as a discord.py Cog. That was fine while Discord was the only adapter,
but ai/handler.py already called check_and_spend/get_status on it as
plain Python methods (it has zero discord.py imports and never touches
the fact that the object is also a Cog) — the "cog-ness" was incidental,
not load-bearing. Now that Telegram needs the exact same spend/status/
insufficient-funds logic, that incidental coupling would force either
duplicating this logic in telegram_bot/, or having Telegram commands
reach into a discord.py Cog instance, which is backwards. Extracting it
here (mirroring core/auth.py and core/memory.py, which were already
platform-agnostic) is the fix: discord_bot/coin_commands.py becomes a
thin slash-command wrapper around this, same shape as
discord_bot/auth_commands.py wraps core/auth.py.

Balance is global per Nebula account, not per guild, per channel, or per
platform — see core/database.py's coin_balances table, which this class
is a thin business-logic wrapper around.
"""
from typing import Dict
from core.database import DatabaseManager


def format_seconds(seconds: int) -> str:
    """Format a seconds count as 'Xh Ym' for human-friendly display."""
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
    """Rules (unchanged from the pre-extraction version):
    - Every Nebula account starts with 10 coins.
    - 1 coin per AI message, 2 coins per search.
    - Balance resets to 10 (not stacked) 8 hours after the last reset.
    - When balance hits 0, the bot refuses and reports time until reset.
    - Admins can grant/set coins via /add_coin (Discord) or an
      equivalent Telegram command, bypassing reset logic.
    """

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
        # NOTE: this string uses Discord-flavored markdown (**bold**),
        # inherited unchanged from the pre-extraction version. Discord
        # renders it correctly. Telegram handlers send it as plain text
        # (see telegram_bot/ — no parse_mode is set on any send call),
        # so on Telegram the asterisks show up literally rather than as
        # bold. This is a deliberate, narrow trade-off: usernames can
        # contain underscores, and several of these shared strings
        # interpolate raw user input, which makes Telegram's Markdown /
        # MarkdownV2 parse modes actively unsafe here (an unescaped `_`
        # in a username makes the send call fail outright, which is a
        # much worse outcome than a literal asterisk). Fixing this
        # properly means either escaping all interpolated values
        # everywhere or making these strings markdown-free at the
        # source — both are bigger changes than this task's scope and
        # both would need to be re-verified against any existing tests
        # asserting on these exact strings, so it's left as-is for now.
        return (
            f"⛔ {display_name}, you're out of coins! "
            f"Next reset in approximately **{format_seconds(seconds_until_reset)}**.\n"
            f"You can ask an admin to give you some coins using /add_coin."
        )
