import discord
from discord import app_commands
from discord.ext import commands

from core.auth import AuthError, SYNC_CODE_EXPIRY_MINUTES

DISCORD_PLATFORM = "discord"

# Which platforms a Discord-linked account can currently generate a sync
# code for. Adding a third platform later (its own /verify-equivalent
# command using core.auth.verify_sync_code) is just adding its name here.
SUPPORTED_SYNC_TARGETS = ["telegram"]


class SyncCommands(commands.Cog):
    """The /sync command: lets an already-approved, Discord-linked
    Nebula account generate a one-time code to link a second platform
    (Telegram today) to the SAME account, without that platform's bot
    needing to message the user first -- which Telegram in particular
    can't do until the user has messaged it at least once.

    Direction is deliberately Discord -> other platform, not the
    reverse: the code is generated here and the user carries it TO the
    other platform's /verify command. See telegram_bot/auth_handlers.py
    for the other half of this flow, and core/auth.py's
    generate_sync_code/verify_sync_code docstrings for why the direction
    is fixed this way.
    """

    def __init__(self, bot):
        self.bot = bot
        self.auth = bot.auth

    @app_commands.command(name='sync', description='Link another platform (e.g. Telegram) to this Nebula account.')
    @app_commands.describe(
        platform='Which platform to link',
        username="Your Nebula username (confirms this is really your account, and is what you'll type again on the other platform)"
    )
    @app_commands.choices(platform=[
        app_commands.Choice(name=p.capitalize(), value=p) for p in SUPPORTED_SYNC_TARGETS
    ])
    async def sync_command(self, interaction: discord.Interaction, platform: app_commands.Choice[str], username: str):
        await interaction.response.defer(ephemeral=True)

        try:
            identity = self.auth.require_approved_identity(DISCORD_PLATFORM, str(interaction.user.id))
        except AuthError as e:
            await interaction.followup.send(str(e), ephemeral=True)
            return

        # Username isn't needed to resolve WHO is asking (that's already
        # resolved above from the caller's Discord identity) -- it's a
        # deliberate double-check the caller knows their own Nebula
        # username correctly, since it's the same value they'll need to
        # type again on the target platform's /verify command.
        if username != identity['username']:
            await interaction.followup.send(
                f"❌ That doesn't match your Nebula username. Your username is "
                f"**{identity['username']}** — use that exact value.",
                ephemeral=True
            )
            return

        target_platform = platform.value
        code = self.auth.generate_sync_code(identity['nebula_user_id'], target_platform)

        await interaction.followup.send(
            f"🔗 Your sync code: **{code}**\n\n"
            f"Go to **{target_platform.capitalize()}**, start a chat with the "
            f"Nebula bot there (send `/start` first if you haven't already), "
            f"then send:\n"
            f"`/verify username:{identity['username']} code:{code}`\n\n"
            f"This code expires in {SYNC_CODE_EXPIRY_MINUTES} minutes and can "
            f"only be used once.",
            ephemeral=True
        )


async def setup(bot):
    await bot.add_cog(SyncCommands(bot))
