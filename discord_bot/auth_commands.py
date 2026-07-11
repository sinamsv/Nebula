import discord
from discord import app_commands
from discord.ext import commands

from core.auth import AuthError

DISCORD_PLATFORM = "discord"


class AuthCommands(commands.Cog):
    """Slash commands for account creation and login, shared across
    platforms via core.auth.AuthManager. This cog is intentionally thin —
    it only translates Discord's interaction objects into calls against
    the platform-agnostic AuthManager and formats the result. All actual
    validation, hashing, and bootstrap logic lives in core/auth.py so a
    future Telegram adapter can offer the identical /signup and /login
    behavior without duplicating it.
    """

    def __init__(self, bot):
        self.bot = bot
        self.auth = bot.auth

    @app_commands.command(
        name='signup',
        description='Create your Nebula account (shared across Discord, Telegram, etc).'
    )
    @app_commands.describe(
        username='3-32 characters: letters, numbers, underscores only',
        password='At least 8 characters. This is sent as a command parameter — use a password unique to Nebula.',
        bootstrap_key='(Admin setup only) One-time ADMIN_BOOTSTRAP_KEY from .env, to claim the first admin account'
    )
    async def signup_command(
        self,
        interaction: discord.Interaction,
        username: str,
        password: str,
        bootstrap_key: str = None
    ):
        """Create a new Nebula account and link it to the caller's Discord
        identity immediately, so they can start using the bot right away
        (pending approval, unless this is the bootstrap admin claim)."""
        # Deferred + ephemeral: the password parameter is visible in
        # Discord's own audit log/slash command history regardless of what
        # we do here — that's a platform limitation we can't fully hide.
        # Ephemeral at least keeps it out of the channel for other members.
        await interaction.response.defer(ephemeral=True)

        try:
            result = self.auth.signup(
                username=username,
                password=password,
                display_name=interaction.user.display_name,
                platform=DISCORD_PLATFORM,
                platform_user_id=str(interaction.user.id),
                platform_display_name=interaction.user.display_name,
                bootstrap_key=bootstrap_key,
            )
        except AuthError as e:
            await interaction.followup.send(str(e), ephemeral=True)
            return

        if result['became_admin']:
            await interaction.followup.send(
                f"✅ Account **{result['username']}** created and linked to your Discord "
                f"identity.\n👑 You claimed the bootstrap key and are now Nebula's first "
                f"**admin** — approved automatically. Use `/add_admin` to promote others "
                f"and `/approve_user` to review future signups.",
                ephemeral=True
            )
            return

        await interaction.followup.send(
            f"✅ Account **{result['username']}** created and linked to your Discord identity.\n"
            f"⏳ Your account is **pending approval** from an admin before you can chat "
            f"with Nebula or use tools. You'll be able to tell once you're approved — "
            f"just try mentioning the bot.",
            ephemeral=True
        )

    @app_commands.command(
        name='login',
        description='Log in to your existing Nebula account from this platform.'
    )
    @app_commands.describe(
        username='Your Nebula username',
        password='Your Nebula password'
    )
    async def login_command(self, interaction: discord.Interaction, username: str, password: str):
        """Link the caller's Discord identity to an existing Nebula account
        after verifying credentials."""
        await interaction.response.defer(ephemeral=True)

        try:
            result = self.auth.login(
                username=username,
                password=password,
                platform=DISCORD_PLATFORM,
                platform_user_id=str(interaction.user.id),
                platform_display_name=interaction.user.display_name,
            )
        except AuthError as e:
            await interaction.followup.send(str(e), ephemeral=True)
            return

        if not result['is_approved']:
            await interaction.followup.send(
                f"✅ Logged in as **{result['username']}** and linked to this Discord "
                f"identity.\n⏳ Note: this account is still pending admin approval, so "
                f"Nebula won't respond to you yet.",
                ephemeral=True
            )
            return

        await interaction.followup.send(
            f"✅ Logged in as **{result['username']}** and linked to this Discord identity. "
            f"Your memory and coin balance carry over from any other platform you've used "
            f"Nebula on.",
            ephemeral=True
        )


async def setup(bot):
    """Setup function to load the cog."""
    await bot.add_cog(AuthCommands(bot))
