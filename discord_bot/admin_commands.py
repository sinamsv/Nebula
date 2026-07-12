import discord
from discord import app_commands
from discord.ext import commands

from core.auth import AuthError

DISCORD_PLATFORM = "discord"


class AdminCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db
        self.auth = bot.auth

    def _require_admin_identity(self, discord_user_id: int):
        identity = self.auth.resolve_identity(DISCORD_PLATFORM, str(discord_user_id))
        if identity is None:
            raise AuthError(
                "❌ You need a Nebula account to do that. Use `/signup` or `/login` first."
            )
        if not identity['is_approved']:
            raise AuthError("❌ Your Nebula account is still pending approval.")
        if not identity['is_admin']:
            raise AuthError("❌ Only Nebula admins can do that.")
        return identity

    @app_commands.command(name='approve_user', description='[Admin] Approve or reject a pending Nebula account.')
    @app_commands.describe(username='The Nebula username to approve or reject', approve='True to approve, False to reject')
    async def approve_user_command(self, interaction: discord.Interaction, username: str, approve: bool):
        try:
            approver = self._require_admin_identity(interaction.user.id)
        except AuthError as e:
            await interaction.response.send_message(str(e), ephemeral=True)
            return

        try:
            result = self.auth.approve_user(
                target_username=username, approve=approve,
                approver_nebula_user_id=approver['nebula_user_id'],
                approver_display_name=interaction.user.display_name,
            )
        except AuthError as e:
            await interaction.response.send_message(str(e), ephemeral=True)
            return

        verb = "approved ✅" if result['approved'] else "rejected ❌"
        await interaction.response.send_message(f"Nebula account **{result['username']}** has been {verb}.")

    @app_commands.command(name='pending_users', description='[Admin] List Nebula accounts awaiting approval.')
    async def pending_users_command(self, interaction: discord.Interaction):
        try:
            self._require_admin_identity(interaction.user.id)
        except AuthError as e:
            await interaction.response.send_message(str(e), ephemeral=True)
            return

        pending = self.auth.list_pending(limit=25)
        if not pending:
            await interaction.response.send_message("✅ No pending accounts. Everyone's approved.", ephemeral=True)
            return

        embed = discord.Embed(title="⏳ Pending Nebula Accounts", color=discord.Color.orange())
        for p in pending[:25]:
            embed.add_field(
                name=p['username'],
                value=f"Display name: {p['display_name']}\nSigned up: {p['created_at']}",
                inline=False
            )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name='add_admin', description="[Admin] Promote a Nebula user to admin.")
    @app_commands.describe(username='The Nebula username to promote to admin')
    async def add_admin_command(self, interaction: discord.Interaction, username: str):
        try:
            granter = self._require_admin_identity(interaction.user.id)
        except AuthError as e:
            await interaction.response.send_message(str(e), ephemeral=True)
            return

        try:
            result = self.auth.add_admin(
                target_username=username,
                granter_nebula_user_id=granter['nebula_user_id'],
                granter_display_name=interaction.user.display_name,
            )
        except AuthError as e:
            await interaction.response.send_message(str(e), ephemeral=True)
            return

        await interaction.response.send_message(f"👑 **{result['username']}** is now a Nebula admin.")

    @app_commands.command(name='admin_logs', description='[Admin] View recent admin action logs.')
    @app_commands.describe(limit='Number of log entries to show (max 50, default 10)')
    async def admin_logs(self, interaction: discord.Interaction, limit: int = 10):
        try:
            self._require_admin_identity(interaction.user.id)
        except AuthError as e:
            await interaction.response.send_message(str(e), ephemeral=True)
            return

        if limit > 50:
            limit = 50
        elif limit < 1:
            limit = 1

        logs = self.db.get_admin_logs(limit)

        if not logs:
            await interaction.response.send_message("No admin logs found.")
            return

        embed = discord.Embed(title="📋 Admin Action Logs", color=discord.Color.gold())
        for i, log in enumerate(logs[:10], 1):
            value = f"**Action:** {log['action_type']}\n"
            if log['target_name']:
                value += f"**Target:** {log['target_name']}\n"
            if log['details']:
                value += f"**Details:** {log['details']}\n"
            value += f"**Time:** {log['timestamp']}"
            embed.add_field(name=f"{i}. {log['admin_name']}", value=value, inline=False)

        await interaction.response.send_message(embed=embed)


async def setup(bot):
    await bot.add_cog(AdminCommands(bot))
