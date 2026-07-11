import discord
from discord import app_commands
from discord.ext import commands

from core.auth import AuthError

DISCORD_PLATFORM = "discord"


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


class CoinManager(commands.Cog):
    """Manages the Nebula Coin rate-limiting system.

    Balance is global per Nebula account, not per guild or per platform.
    A user who spends coins chatting on Discord has fewer coins left when
    they message via Telegram later today — intended behavior for a
    shared cross-platform identity, not a bug.

    This class is still technically a discord.py Cog (so /coin and
    /add_coin work as slash commands), but its check_and_spend/get_status
    helper methods are called directly by ai/handler.py as plain Python
    methods on the cog instance — ai/handler.py doesn't know or care that
    this object happens to also be a Discord cog.

    Rules (unchanged from before):
    - Every Nebula account starts with 10 coins.
    - 1 coin per AI message, 2 coins per search.
    - Balance resets to 10 (not stacked) 8 hours after the last reset.
    - When balance hits 0, the bot refuses and reports time until reset.
    - Admins can grant/set coins via /add_coin, bypassing reset logic.
    """

    MESSAGE_COST = 1
    SEARCH_COST = 2
    IMAGE_COST = 5

    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db
        self.auth = bot.auth

    # ------------------------------------------------------------------
    # Helpers used by ai/handler.py — keyed purely on nebula_user_id.
    # ------------------------------------------------------------------

    def check_and_spend(self, nebula_user_id: int, amount: int) -> dict:
        return self.db.spend_coins(nebula_user_id, amount)

    def get_status(self, nebula_user_id: int) -> dict:
        return self.db.get_coin_status(nebula_user_id)

    def insufficient_funds_message(self, display_name: str, seconds_until_reset: int) -> str:
        return (
            f"⛔ {display_name}, you're out of coins! "
            f"Next reset in approximately **{format_seconds(seconds_until_reset)}**.\n"
            f"You can ask an admin to give you some coins using `/add_coin`."
        )

    # ------------------------------------------------------------------
    # Slash Commands
    # ------------------------------------------------------------------

    @app_commands.command(name='coin', description='Show your current Nebula Coin balance and time until reset.')
    async def coin_command(self, interaction: discord.Interaction):
        try:
            identity = self.auth.require_approved_identity(DISCORD_PLATFORM, str(interaction.user.id))
        except AuthError as e:
            await interaction.response.send_message(str(e), ephemeral=True)
            return

        status = self.get_status(identity['nebula_user_id'])
        balance = status['balance']
        seconds_until_reset = status['seconds_until_reset']

        embed = discord.Embed(
            title="🌝 Nebula Coin",
            color=discord.Color.gold() if balance > 0 else discord.Color.red()
        )
        embed.add_field(name="Current Balance", value=f"{balance} coins", inline=True)
        embed.add_field(name="Time Until Reset", value=format_seconds(seconds_until_reset), inline=True)
        embed.set_footer(
            text=f"Each message costs {self.MESSAGE_COST} coin, each search costs "
                 f"{self.SEARCH_COST} coins, and each image costs {self.IMAGE_COST} coins. "
                 f"Balance is shared across every platform linked to your account."
        )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name='add_coin', description="[Admin] Add to or set a Nebula user's coin balance.")
    @app_commands.describe(
        username='The Nebula username whose balance you want to modify',
        amount='The amount of coins to add or set',
        mode='Whether to add this amount to the current balance, or set the balance to this exact amount'
    )
    @app_commands.choices(mode=[
        app_commands.Choice(name='add', value='add'),
        app_commands.Choice(name='set', value='set'),
    ])
    async def add_coin_command(
        self,
        interaction: discord.Interaction,
        username: str,
        amount: int,
        mode: app_commands.Choice[str]
    ):
        """Admin-only: add to or set a Nebula user's coin balance, looked
        up by Nebula username (not Discord member) since the balance
        isn't guild-scoped anymore — the target may not even be in this
        Discord server."""
        try:
            admin_identity = self.auth.resolve_identity(DISCORD_PLATFORM, str(interaction.user.id))
            if admin_identity is None or not admin_identity['is_approved']:
                await interaction.response.send_message(
                    "❌ You need an approved Nebula account to do that.", ephemeral=True
                )
                return
            if not admin_identity['is_admin']:
                await interaction.response.send_message("❌ Only Nebula admins can do that.", ephemeral=True)
                return
        except AuthError as e:
            await interaction.response.send_message(str(e), ephemeral=True)
            return

        target = self.db.get_user_by_username(username)
        if not target:
            await interaction.response.send_message(
                f"❌ No Nebula account found with username **{username}**.", ephemeral=True
            )
            return

        mode_value = mode.value
        new_balance = self.db.modify_coins(target['nebula_user_id'], amount, mode_value)

        self.db.log_admin_action(
            admin_identity['nebula_user_id'], interaction.user.display_name,
            "add_coin", target['nebula_user_id'], target['display_name'],
            f"mode={mode_value}, amount={amount}, new_balance={new_balance}"
        )

        verb = "added to" if mode_value == "add" else "set for"
        await interaction.response.send_message(
            f"✅ Coins **{verb}** {target['display_name']} (**{username}**). "
            f"New balance: **{new_balance}** coins."
        )


async def setup(bot):
    """Setup function to load the cog."""
    await bot.add_cog(CoinManager(bot))
