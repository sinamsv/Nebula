import discord
from discord.ext import commands

from core.auth import AuthError

DISCORD_PLATFORM = "discord"


class SearchCommand(commands.Cog):
    """The `/search` slash command and the "search disabled" admin
    notifier.

    All actual search provider logic (Google Custom Search vs Tavily,
    credential checks, no-fallback-on-misconfiguration) lives in
    tools/search.py and is shared with ai/handler.py's `search` tool —
    this cog just wraps bot.search_tool.perform_search() for the direct
    slash-command path and handles the Discord-specific parts: coin
    spending tied to a Discord-originated request, message chunking for
    Discord's 2000-char limit, and DMing admins.
    """

    def __init__(self, bot):
        self.bot = bot
        self.search_tool = bot.search_tool
        self.auth = bot.auth
        self.coin_manager = None

        # Ensures the "search disabled" DM is only sent once per bot run.
        self._admin_notice_sent = False

    async def notify_admins_if_disabled(self):
        """Send a one-time DM to every Nebula admin the bot shares a
        Discord server with, warning that search is disabled due to a
        missing API key. Called once from discord_bot/client.py's
        on_ready handler. Safe to call multiple times; only sends once
        per bot run.

        Recipients are Nebula admins (is_admin on nebula_users, resolved
        via their linked Discord identity), not just anyone with
        Discord's own Administrator permission.
        """
        if self.search_tool.enabled or self._admin_notice_sent:
            return

        self._admin_notice_sent = True
        message = (
            "⚠️ **Nebula Search Disabled**\n"
            f"{self.search_tool.disabled_reason}\n\n"
            "No search provider is currently active, so the search tool "
            "will not respond to search requests until this is fixed."
        )

        notified_discord_ids = set()
        for guild in self.bot.guilds:
            for member in guild.members:
                if member.bot or member.id in notified_discord_ids:
                    continue
                identity = self.auth.resolve_identity(DISCORD_PLATFORM, str(member.id))
                if not identity or not identity['is_admin']:
                    continue
                notified_discord_ids.add(member.id)
                try:
                    await member.send(message)
                except discord.Forbidden:
                    pass
                except Exception as e:
                    print(f"Failed to DM admin {member.display_name} about disabled search: {e}")

    @commands.command(name='search')
    async def search_command(self, ctx, *, query: str):
        """Perform a web search using the configured provider. Requires an
        approved Nebula identity; spends SEARCH_COST coins from the
        caller's global Nebula balance."""
        try:
            identity = self.auth.require_approved_identity(DISCORD_PLATFORM, str(ctx.author.id))
        except AuthError as e:
            await ctx.send(str(e))
            return

        if not self.coin_manager:
            self.coin_manager = self.bot.get_cog('CoinManager')

        if self.coin_manager:
            spend_result = self.coin_manager.check_and_spend(
                identity['nebula_user_id'], self.coin_manager.SEARCH_COST
            )
            if not spend_result['success']:
                await ctx.send(
                    self.coin_manager.insufficient_funds_message(
                        ctx.author.display_name,
                        spend_result['seconds_until_reset']
                    )
                )
                return

        async with ctx.typing():
            results = await self.search_tool.perform_search(query)

        if len(results) <= 2000:
            await ctx.send(results)
        else:
            chunks = []
            current_chunk = ""
            for line in results.split('\n'):
                if len(current_chunk) + len(line) + 1 <= 2000:
                    current_chunk += line + '\n'
                else:
                    if current_chunk:
                        chunks.append(current_chunk.strip())
                    current_chunk = line + '\n'
            if current_chunk:
                chunks.append(current_chunk.strip())
            for chunk in chunks:
                await ctx.send(chunk)


async def setup(bot):
    """Setup function to load the cog."""
    await bot.add_cog(SearchCommand(bot))
