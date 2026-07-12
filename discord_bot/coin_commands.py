import discord
from discord import app_commands
from discord.ext import commands

from core.auth import AuthError
from core.coins import format_seconds

DISCORD_PLATFORM = "discord"


class CoinCommands(commands.Cog):
    """The /coin and /add_coin slash commands.

    All actual balance/reset/spend logic lives in core.coins.CoinManager
    (shared with Telegram and with ai/handler.py's per-turn spending) --
    this cog is a thin Discord-specific presentation layer around it,
    the same shape as AuthCommands wraps core.auth.AuthManager and
    MemoryCommands wraps core.memory.MemoryManager.

    Previously this class WAS the shared coin-logic object (a discord.py
    Cog doing double duty as ai/handler.py's coin dependency too),
    looked up elsewhere via bot.get_cog('CoinManager'). That only worked
    because Discord was the sole adapter. Now that Telegram needs the
    same logic, the shared object is core.coins.CoinManager
    (bot.coin_manager, constructed once in main.py and passed to every
    adapter + AIHandler directly, no cog lookup involved) -- this cog
    just wraps slash commands around it.
    """

    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db
        self.auth = bot.auth
        self.coins = bot.coin_manager  # core.coins.CoinManager, shared instance

    @app_commands.command(name='coin', description='Show your current Nebula Coin balance and time until reset.')
    async def coin_command(self, interaction: discord.Interaction):
        try:
            identity = self.auth.require_approved_identity(DISCORD_PLATFORM, str(interaction.user.id))
        except AuthError as e:
            await interaction.response.send_message(str(e), ephemeral=True)
            return

        status = self.coins.get_status(identity['nebula_user_id'])
        balance = status['balance']
        seconds_until_reset = status['seconds_until_reset']

        embed = discord.Embed(
            title="🌝 Nebula Coin",
            color=discord.Color.gold() if balance > 0 else discord.Color.red()
        )
        embed.add_field(name="Current Balance", value=f"{balance} coins", inline=True)
        embed.add_field(name="Time Until Reset", value=format_seconds(seconds_until_reset), inline=True)
        embed.set_footer(
            text=f"Each message costs {self.coins.MESSAGE_COST} coin, each search costs "
                 f"{self.coins.SEARCH_COST} coins, and each image costs {self.coins.IMAGE_COST} coins. "
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
    async def add_coin_command(self, interaction: discord.Interaction, username: str, amount: int, mode: app_commands.Choice[str]):
        try:
            admin_identity = self.auth.resolve_identity(DISCORD_PLATFORM, str(interaction.user.id))
            if admin_identity is None or not admin_identity['is_approved']:
                await interaction.response.send_message("❌ You need an approved Nebula account to do that.", ephemeral=True)
                return
            if not admin_identity['is_admin']:
                await interaction.response.send_message("❌ Only Nebula admins can do that.", ephemeral=True)
                return
        except AuthError as e:
            await interaction.response.send_message(str(e), ephemeral=True)
            return

        target = self.db.get_user_by_username(username)
        if not target:
            await interaction.response.send_message(f"❌ No Nebula account found with username **{username}**.", ephemeral=True)
            return

        mode_value = mode.value
        new_balance = self.coins.modify_coins(target['nebula_user_id'], amount, mode_value)

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
    await bot.add_cog(CoinCommands(bot))
