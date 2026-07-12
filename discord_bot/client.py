import os
import discord
from discord.ext import commands

from core.database import DatabaseManager
from core.auth import AuthManager
from core.memory import MemoryManager
from core.coins import CoinManager
from tools.search import SearchTool
from ai.handler import AIHandler

DISCORD_PLATFORM = "discord"


def build_bot(db: DatabaseManager, auth: AuthManager, memory: MemoryManager,
              coin_manager: CoinManager, search_tool: SearchTool,
              ai_handler: AIHandler) -> commands.Bot:
    """Construct a fully-wired discord.py Bot around instances built ONCE
    in main.py and shared with every other adapter.

    This is what actually makes cross-platform identity/memory/coins
    work: Discord and Telegram both read and write through the SAME
    DatabaseManager (and therefore the same underlying sqlite file),
    rather than each adapter opening its own connection pool to
    logically-separate state. Previously (single-adapter phase) this
    function constructed db/auth/memory/search_tool itself; now main.py
    owns that and hands the results in here, mirroring exactly what its
    own module docstring already sketched for this transition.
    """
    intents = discord.Intents.default()
    intents.message_content = True
    intents.members = True
    intents.guilds = True

    bot = commands.Bot(command_prefix="!", intents=intents)

    bot.db = db
    bot.auth = auth
    bot.memory = memory
    bot.coin_manager = coin_manager
    bot.search_tool = search_tool
    # Unlike before, this is never None-then-set-later inside on_ready --
    # AIHandler no longer depends on any cog having loaded first (that
    # dependency only existed because CoinManager used to BE a cog; now
    # it's core.coins.CoinManager, constructed alongside everything else
    # in main.py before any adapter even starts).
    bot.ai_handler = ai_handler

    @bot.event
    async def on_ready():
        print(f'{bot.user} has connected to Discord!')
        print(f'Bot is in {len(bot.guilds)} guilds')

        if not os.getenv('ADMIN_BOOTSTRAP_KEY'):
            print(
                "WARNING: ADMIN_BOOTSTRAP_KEY is not set. No one will be able to "
                "claim the first admin account via /signup. Set a long random "
                "value in .env before your first real user signs up."
            )
        elif bot.db.is_bootstrap_claimed():
            print("Admin bootstrap key already claimed — this is expected after first setup.")
        else:
            print("Admin bootstrap key is set and unclaimed — first /signup with it becomes admin.")

        await _load_cogs(bot)
        await _sync_slash_commands(bot)

        search_tool_cog = bot.get_cog('SearchCommand')
        if search_tool_cog:
            await search_tool_cog.notify_admins_if_disabled()

    @bot.event
    async def on_message(message):
        if message.author == bot.user:
            return
        # discord.py automatically dispatches on_message to cog listeners
        # (message_listener.py's handling) without anything else needed here.
        pass

    return bot


async def _load_cogs(bot: commands.Bot):
    cogs_list = [
        'discord_bot.auth_commands',
        'discord_bot.memory_commands',
        'discord_bot.coin_commands',
        'discord_bot.sync_commands',
        'discord_bot.admin_commands',
        'discord_bot.search_command',
        'discord_bot.message_listener',
    ]
    for cog in cogs_list:
        try:
            await bot.load_extension(cog)
            print(f'Loaded {cog}')
        except Exception as e:
            print(f'Failed to load {cog}: {e}')


async def _sync_slash_commands(bot: commands.Bot):
    """Sync slash (app) commands with Discord. Global syncs can take up
    to an hour to propagate; set DEV_GUILD_ID in .env for instant sync to
    one test server during development."""
    dev_guild_id = os.getenv('DEV_GUILD_ID')
    try:
        if dev_guild_id:
            guild = discord.Object(id=int(dev_guild_id))
            bot.tree.copy_global_to(guild=guild)
            synced = await bot.tree.sync(guild=guild)
            print(f'Synced {len(synced)} slash commands to dev guild {dev_guild_id}')
        else:
            synced = await bot.tree.sync()
            print(f'Synced {len(synced)} slash commands globally (may take up to 1 hour to propagate)')
    except Exception as e:
        print(f'Failed to sync slash commands: {e}')


async def start(bot: commands.Bot, token: str):
    """Async-friendly entry point for main.py's asyncio.gather().

    Unlike the old run() (removed), this doesn't call asyncio.run()
    internally to manage its own event loop -- it's meant to be awaited
    alongside the Telegram adapter under ONE shared loop. `async with
    bot:` here mirrors exactly what discord.py's own Client.run() does
    internally (it wraps start() in `async with self:` to handle setup/
    teardown of the bot's internal aiohttp session correctly) -- so
    behavior is unchanged, just no longer blocking/loop-owning.
    """
    if not token:
        print("ERROR: DISCORD_TOKEN not set — Discord adapter cannot start.")
        return

    async with bot:
        await bot.start(token)
