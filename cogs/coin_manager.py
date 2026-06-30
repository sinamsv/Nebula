import discord
from discord import app_commands
from discord.ext import commands
from database import DatabaseManager


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

    Rules:
    - Every user starts with 10 coins per guild.
    - 1 coin is spent per AI message, 2 coins per search.
    - Balance resets to 10 (not stacked) 8 hours after the user's last reset point.
    - When balance hits 0 (or below), the bot refuses to respond and tells
      the user how long until their coins reset.
    - Admins can grant/set coins via /add_coin, bypassing the reset logic.
    """

    MESSAGE_COST = 1
    SEARCH_COST = 2
    IMAGE_COST = 5

    def __init__(self, bot):
        self.bot = bot
        self.db = DatabaseManager()

    # ------------------------------------------------------------------
    # Helpers used by other cogs (AIHandler, SearchTool)
    # ------------------------------------------------------------------

    def check_and_spend(self, user_id: str, guild_id: str, amount: int) -> dict:
        """Try to spend `amount` coins for a user. Returns the result dict
        from DatabaseManager.spend_coins:
        {'success': bool, 'balance': int, 'seconds_until_reset': int}
        """
        return self.db.spend_coins(user_id, guild_id, amount)

    def get_status(self, user_id: str, guild_id: str) -> dict:
        """Get current balance + time-until-reset without spending anything."""
        return self.db.get_coin_status(user_id, guild_id)

    def insufficient_funds_message(self, display_name: str, seconds_until_reset: int) -> str:
        """Standard message shown when a user has no coins left."""
        return (
            f"⛔ {display_name}, you're out of coins! "
            f"Next reset in approximately **{format_seconds(seconds_until_reset)}**.\n"
            f"You can ask an admin to give you some coins using `/add_coin`."
        )

    # ------------------------------------------------------------------
    # Slash Commands
    # ------------------------------------------------------------------

    @app_commands.command(name='coin', description='Show your current Nebula Coin balance and time until reset.')
    @app_commands.guild_only()
    async def coin_command(self, interaction: discord.Interaction):
        """Show the current user's Nebula Coin balance and time until reset."""
        user_id = str(interaction.user.id)
        guild_id = str(interaction.guild.id)

        status = self.get_status(user_id, guild_id)
        balance = status['balance']
        seconds_until_reset = status['seconds_until_reset']

        embed = discord.Embed(
            title="🌝 Nebula Coin",
            color=discord.Color.gold() if balance > 0 else discord.Color.red()
        )
        embed.add_field(name="Current Balance", value=f"{balance} coins", inline=True)
        embed.add_field(
            name="Time Until Reset",
            value=format_seconds(seconds_until_reset),
            inline=True
        )
        embed.set_footer(text=f"Each message costs {self.MESSAGE_COST} coin, each search costs {self.SEARCH_COST} coins, and each image costs {self.IMAGE_COST} coins.")

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name='add_coin', description="[Admin] Add to or set a user's Nebula Coin balance.")
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(
        member='The user whose balance you want to modify',
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
        member: discord.Member,
        amount: int,
        mode: app_commands.Choice[str]
    ):
        """Admin-only: add to or set a user's coin balance.

        Usage:
          /add_coin member:@user amount:5 mode:add   -> adds 5 coins to current balance
          /add_coin member:@user amount:5 mode:set   -> sets balance to exactly 5
        """
        mode_value = mode.value

        guild_id = str(interaction.guild.id)
        user_id = str(member.id)

        new_balance = self.db.modify_coins(user_id, guild_id, amount, mode_value)

        # Log the action for audit purposes
        self.db.log_admin_action(
            guild_id,
            str(interaction.user.id),
            interaction.user.display_name,
            "add_coin",
            user_id,
            member.display_name,
            f"mode={mode_value}, amount={amount}, new_balance={new_balance}"
        )

        verb = "added to" if mode_value == "add" else "set for"
        await interaction.response.send_message(
            f"✅ Coins **{verb}** {member.display_name}. New balance: **{new_balance}** coins."
        )

    @add_coin_command.error
    async def add_coin_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message("❌ Only administrators can use this command.", ephemeral=True)
        else:
            await interaction.response.send_message(f"❌ Error: {str(error)}", ephemeral=True)


async def setup(bot):
    """Setup function to load the cog."""
    await bot.add_cog(CoinManager(bot))
