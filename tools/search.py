"""Platform-agnostic web search tool.

Supports two interchangeable providers: Google Custom Search and Tavily
(an AI-native search API). Which provider is used is controlled by the
SEARCH_PROVIDER environment variable ('google' or 'tavily', defaults to
'google'). Both providers' credentials can be configured at the same
time; only the selected one is used.

Enablement rule (deliberately simple, no automatic fallback):
- If the credentials for the SELECTED provider are missing, the entire
  search tool is disabled, even if the other provider's credentials are
  present.
- If the selected provider's credentials ARE present, search proceeds
  normally with that provider. No mixing within a single request.

This module has zero discord.py (or any platform SDK) imports. Any
adapter — discord_bot/, a future telegram_bot/, a future API server —
imports SearchTool directly and calls perform_search(). The Discord
slash command wrapper lives in discord_bot/search_command.py and is a
thin pass-through to this.
"""
import aiohttp
import os


class SearchTool:
    TAVILY_SEARCH_URL = "https://api.tavily.com/search"
    GOOGLE_SEARCH_URL = "https://www.googleapis.com/customsearch/v1"

    VALID_PROVIDERS = ("google", "tavily")

    def __init__(self):
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
    # Provider-agnostic entry point
    # ------------------------------------------------------------------

    async def perform_search(self, query: str, num_results: int = 5) -> str:
        """Perform a web search using whichever provider is configured.
        Callers don't need to know or care which provider is behind this."""
        if not self.enabled:
            return f"❌ Web search is currently disabled. {self.disabled_reason}"

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
