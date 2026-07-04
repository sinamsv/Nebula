import discord
from discord.ext import commands
import aiohttp
import os


class SearchTool(commands.Cog):
    """Web search integration supporting two interchangeable providers:
    Google Custom Search and Tavily (an AI-native search API).

    Which provider is actually used is controlled by the SEARCH_PROVIDER
    environment variable ('google' or 'tavily', defaults to 'google').
    Both providers' credentials can be configured at the same time; only
    the selected one is used. Google is never removed from the codebase,
    since keeping both wired up is what gives flexibility to switch later.

    Enablement rule (deliberately simple, no automatic fallback):
    - If the credentials for the SELECTED provider are missing, the entire
      search tool is disabled, even if the other provider's credentials
      are present. Administrators are notified once via DM (see bot.py /
      on_ready wiring) so a misconfiguration doesn't go unnoticed.
    - If the selected provider's credentials ARE present, search proceeds
      normally with that provider. No mixing within a single request.
    """

    TAVILY_SEARCH_URL = "https://api.tavily.com/search"
    GOOGLE_SEARCH_URL = "https://www.googleapis.com/customsearch/v1"

    VALID_PROVIDERS = ("google", "tavily")

    def __init__(self, bot):
        self.bot = bot
        self.coin_manager = None

        # Google credentials
        self.google_api_key = os.getenv('GOOGLE_SEARCH_API_KEY')
        self.google_engine_id = os.getenv('GOOGLE_SEARCH_ENGINE_ID')

        # Tavily credentials
        self.tavily_api_key = os.getenv('TAVILY_API_KEY')

        # Which provider the user wants (defaults to google for backwards
        # compatibility with existing .env files that predate this feature)
        raw_provider = os.getenv('SEARCH_PROVIDER', 'google').strip().lower()
        if raw_provider not in self.VALID_PROVIDERS:
            print(
                f"WARNING: Unknown SEARCH_PROVIDER '{raw_provider}', "
                f"falling back to 'google'. Valid values: {self.VALID_PROVIDERS}"
            )
            raw_provider = 'google'
        self.provider = raw_provider

        # Determine enabled/disabled state up front based on the selected
        # provider's credentials only (no cross-provider fallback).
        self.enabled, self.disabled_reason = self._check_configuration()

        # Ensures the "search disabled" DM is only sent once per bot run,
        # not once per guild or per message.
        self._admin_notice_sent = False

        if self.enabled:
            print(f"Search tool enabled using provider: {self.provider}")
        else:
            print(f"WARNING: Search tool disabled - {self.disabled_reason}")

    def _check_configuration(self):
        """Determine whether the currently selected provider is usable.
        Returns (enabled: bool, reason: str | None)."""
        if self.provider == 'tavily':
            if self.tavily_api_key:
                return True, None
            return False, (
                "SEARCH_PROVIDER is set to 'tavily' but TAVILY_API_KEY is "
                "missing. Set TAVILY_API_KEY in your .env file to enable search."
            )
        else:  # google
            if self.google_api_key and self.google_engine_id:
                return True, None
            missing = []
            if not self.google_api_key:
                missing.append("GOOGLE_SEARCH_API_KEY")
            if not self.google_engine_id:
                missing.append("GOOGLE_SEARCH_ENGINE_ID")
            return False, (
                f"SEARCH_PROVIDER is set to 'google' but {', '.join(missing)} "
                f"{'is' if len(missing) == 1 else 'are'} missing. Set "
                f"{'it' if len(missing) == 1 else 'them'} in your .env file to enable search."
            )

    # ------------------------------------------------------------------
    # Provider-agnostic entry point (unchanged signature/behavior from the
    # AI handler and search command's point of view)
    # ------------------------------------------------------------------

    async def perform_search(self, query: str, num_results: int = 5) -> str:
        """Perform a web search using whichever provider is configured.
        Callers (ai_handler.py, search_command) don't need to know or care
        which provider is behind this."""
        if not self.enabled:
            return (
                f"❌ Web search is currently disabled. {self.disabled_reason}"
            )

        try:
            if self.provider == 'tavily':
                return await self._search_tavily(query, num_results)
            else:
                return await self._search_google(query, num_results)
        except Exception as e:
            return f"❌ Error performing search: {str(e)}"

    # ------------------------------------------------------------------
    # Google Custom Search
    # ------------------------------------------------------------------

    async def _search_google(self, query: str, num_results: int) -> str:
        params = {
            'key': self.google_api_key,
            'cx': self.google_engine_id,
            'q': query,
            'num': min(num_results, 10)
        }

        async with aiohttp.ClientSession() as session:
            async with session.get(self.GOOGLE_SEARCH_URL, params=params) as response:
                if response.status != 200:
                    return f"❌ Search failed with status code: {response.status}"
                data = await response.json()

        if 'items' not in data or len(data['items']) == 0:
            return f"🔍 No results found for: **{query}**"

        results_text = f"🔍 **Search Results for:** {query}\n\n"
        for i, item in enumerate(data['items'][:num_results], 1):
            title = item.get('title', 'No title')
            link = item.get('link', '')
            snippet = item.get('snippet', 'No description')

            results_text += f"**{i}. {title}**\n"
            results_text += f"{snippet}\n"
            results_text += f"🔗 {link}\n\n"

        return results_text

    # ------------------------------------------------------------------
    # Tavily (AI-native search API)
    # ------------------------------------------------------------------

    async def _search_tavily(self, query: str, num_results: int) -> str:
        headers = {
            'Authorization': f'Bearer {self.tavily_api_key}',
            'Content-Type': 'application/json'
        }
        payload = {
            'query': query,
            'max_results': min(num_results, 10),
            'search_depth': 'basic'
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(self.TAVILY_SEARCH_URL, json=payload, headers=headers) as response:
                if response.status == 401:
                    return "❌ Tavily search failed: invalid or missing API key."
                if response.status != 200:
                    return f"❌ Search failed with status code: {response.status}"
                data = await response.json()

        results = data.get('results', [])
        if not results:
            return f"🔍 No results found for: **{query}**"

        results_text = f"🔍 **Search Results for:** {query}\n\n"
        for i, item in enumerate(results[:num_results], 1):
            title = item.get('title', 'No title')
            link = item.get('url', '')
            snippet = item.get('content', 'No description')

            results_text += f"**{i}. {title}**\n"
            results_text += f"{snippet}\n"
            results_text += f"🔗 {link}\n\n"

        return results_text

    # ------------------------------------------------------------------
    # Admin notification when search is disabled due to misconfiguration
    # ------------------------------------------------------------------

    async def notify_admins_if_disabled(self):
        """Send a one-time DM to every administrator in every guild the bot
        is in, warning that search is disabled due to a missing API key.
        Intended to be called once from bot.py's on_ready handler, after
        guilds/members are populated. Safe to call multiple times; only
        sends once per bot run."""
        if self.enabled or self._admin_notice_sent:
            return

        self._admin_notice_sent = True
        message = (
            "⚠️ **Nebula Search Disabled**\n"
            f"{self.disabled_reason}\n\n"
            "No search provider is currently active, so the search tool "
            "will not respond to search requests until this is fixed."
        )

        for guild in self.bot.guilds:
            for member in guild.members:
                if member.bot:
                    continue
                if member.guild_permissions.administrator:
                    try:
                        await member.send(message)
                    except discord.Forbidden:
                        # User has DMs disabled or blocked the bot; skip silently.
                        pass
                    except Exception as e:
                        print(f"Failed to DM admin {member.display_name} about disabled search: {e}")

    # ------------------------------------------------------------------
    # Commands
    # ------------------------------------------------------------------

    @commands.command(name='search')
    async def search_command(self, ctx, *, query: str):
        """Perform a web search using the configured provider."""
        # --- Nebula Coin check: search costs coins even via direct command ---
        if not self.coin_manager:
            self.coin_manager = self.bot.get_cog('CoinManager')

        if self.coin_manager:
            user_id = str(ctx.author.id)
            guild_id = str(ctx.guild.id)
            spend_result = self.coin_manager.check_and_spend(
                user_id, guild_id, self.coin_manager.SEARCH_COST
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
            results = await self.perform_search(query)

        # Split long messages if needed
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
    await bot.add_cog(SearchTool(bot))
