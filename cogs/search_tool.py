import discord
from discord.ext import commands
import aiohttp
import os

class SearchTool(commands.Cog):
    """Google Custom Search integration for web searches."""

    def __init__(self, bot):
        self.bot = bot
        self.api_key = os.getenv('GOOGLE_SEARCH_API_KEY')
        self.search_engine_id = os.getenv('GOOGLE_SEARCH_ENGINE_ID')
        self.coin_manager = None

        if not self.api_key or not self.search_engine_id:
            print("WARNING: Google Search API credentials not configured!")

    async def perform_search(self, query: str, num_results: int = 5) -> str:
        """Perform a Google Custom Search."""
        if not self.api_key or not self.search_engine_id:
            return "❌ Google Search is not configured. Please set GOOGLE_SEARCH_API_KEY and GOOGLE_SEARCH_ENGINE_ID in .env file."

        try:
            url = "https://www.googleapis.com/customsearch/v1"
            params = {
                'key': self.api_key,
                'cx': self.search_engine_id,
                'q': query,
                'num': min(num_results, 10)
            }

            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params) as response:
                    if response.status != 200:
                        return f"❌ Search failed with status code: {response.status}"

                    data = await response.json()

            # Check if we got results
            if 'items' not in data or len(data['items']) == 0:
                return f"🔍 No results found for: **{query}**"

            # Format results
            results_text = f"🔍 **Search Results for:** {query}\n\n"

            for i, item in enumerate(data['items'][:num_results], 1):
                title = item.get('title', 'No title')
                link = item.get('link', '')
                snippet = item.get('snippet', 'No description')

                results_text += f"**{i}. {title}**\n"
                results_text += f"{snippet}\n"
                results_text += f"🔗 {link}\n\n"

            return results_text

        except Exception as e:
            return f"❌ Error performing search: {str(e)}"

    @commands.command(name='search')
    async def search_command(self, ctx, *, query: str):
        """Perform a web search using Google Custom Search."""
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
            # Split into chunks
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
