import discord
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
    - Admins can grant/set coins via !add_coin, bypassing the reset logic.
    """

    MESSAGE_COST = 1
    SEARCH_COST = 2

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
            f"You can ask an admin to give you some coins using `!add_coin`."
        )

    # ------------------------------------------------------------------
    # Commands
    # ------------------------------------------------------------------

    @commands.command(name='coin')
    async def coin_command(self, ctx):
        """Show the current user's Nebula Coin balance and time until reset."""
        user_id = str(ctx.author.id)
        guild_id = str(ctx.guild.id)

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
        embed.set_footer(text=f"Each message costs {self.MESSAGE_COST} coin and each search costs {self.SEARCH_COST} coins.")

        await ctx.send(embed=embed)

    @commands.command(name='add_coin')
    @commands.has_permissions(administrator=True)
    async def add_coin_command(self, ctx, member: discord.Member, amount: int, mode: str = "add"):
        """Admin-only: add to or set a user's coin balance.

        Usage:
          !add_coin @user 5 add   -> adds 5 coins to current balance
          !add_coin @user 5 set   -> sets balance to exactly 5
        """
        mode = mode.lower().strip()
        if mode not in ("add", "set"):
            await ctx.send("❌ Invalid mode. Use `add` or `set`. Example: `!add_coin @user 5 add`")
            return

        guild_id = str(ctx.guild.id)
        user_id = str(member.id)

        new_balance = self.db.modify_coins(user_id, guild_id, amount, mode)

        # Log the action for audit purposes
        self.db.log_admin_action(
            guild_id,
            str(ctx.author.id),
            ctx.author.display_name,
            "add_coin",
            user_id,
            member.display_name,
            f"mode={mode}, amount={amount}, new_balance={new_balance}"
        )

        verb = "added to" if mode == "add" else "set for"
        await ctx.send(
            f"✅ Coins **{verb}** {member.display_name}. New balance: **{new_balance}** coins."
        )

    @add_coin_command.error
    async def add_coin_error(self, ctx, error):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("❌ Only administrators can use this command.")
        elif isinstance(error, commands.MemberNotFound):
            await ctx.send("❌ User not found. Please mention a user or provide a valid ID.")
        elif isinstance(error, commands.BadArgument):
            await ctx.send("❌ Invalid input. Correct example: `!add_coin @user 5 add`")
        else:
            await ctx.send(f"❌ Error: {str(error)}")


async def setup(bot):
    """Setup function to load the cog."""
    await bot.add_cog(CoinManager(bot))
