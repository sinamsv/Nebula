import discord
from discord import app_commands
from discord.ext import commands

from core.auth import AuthError

DISCORD_PLATFORM = "discord"


class MemoryCommands(commands.Cog):
    """Slash commands for checking and resetting a Nebula user's own
    conversation memory.

    Memory belongs to the individual Nebula account and is shared across
    every platform they've linked. Because of that, these commands are
    not admin-only — they operate on the CALLER's own memory, which is
    personal data, not a shared server resource. There's no target
    parameter; an admin cannot reset someone else's memory through this
    command, intentionally.
    """

    def __init__(self, bot):
        self.bot = bot
        self.auth = bot.auth
        self.memory = bot.memory

    def _require_identity(self, discord_user_id: int):
        return self.auth.require_approved_identity(DISCORD_PLATFORM, str(discord_user_id))

    @app_commands.command(
        name='memory_stats',
        description='Show your Nebula memory usage (shared across all platforms you use).'
    )
    async def memory_stats(self, interaction: discord.Interaction):
        try:
            identity = self._require_identity(interaction.user.id)
        except AuthError as e:
            await interaction.response.send_message(str(e), ephemeral=True)
            return

        stats = self.memory.get_usage(identity['nebula_user_id'])

        embed = discord.Embed(
            title="💾 Your Nebula Memory Usage",
            color=discord.Color.red() if stats['is_full'] else discord.Color.blue()
        )
        embed.add_field(name="Total Tokens Used", value=f"{stats['total_tokens']:,}", inline=True)
        embed.add_field(name="Tokens Remaining", value=f"{stats['remaining']:,}", inline=True)
        embed.add_field(name="Usage Percentage", value=f"{stats['percentage']}%", inline=True)
        embed.add_field(name="Maximum Capacity", value=f"{stats['max_tokens']:,} tokens", inline=False)
        if stats['is_full']:
            embed.set_footer(text="Memory full — run /memory_reset to keep chatting.")

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(
        name='memory_reset',
        description='Clear your Nebula conversation memory (affects all platforms you use).'
    )
    async def memory_reset(self, interaction: discord.Interaction):
        try:
            identity = self._require_identity(interaction.user.id)
        except AuthError as e:
            await interaction.response.send_message(str(e), ephemeral=True)
            return

        self.memory.reset_memory(identity['nebula_user_id'])

        embed = discord.Embed(
            title="🔄 Memory Reset",
            description=(
                "Your Nebula conversation memory has been cleared. This affects "
                "every platform you've linked to this account, not just Discord."
            ),
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot):
    """Setup function to load the cog."""
    await bot.add_cog(MemoryCommands(bot))
