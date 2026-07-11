import os
import discord
from discord.ext import commands

from core.database import DatabaseManager
from core.auth import AuthManager
from core.memory import MemoryManager
from tools.search import SearchTool
from ai.handler import AIHandler

DISCORD_PLATFORM = "discord"


def build_bot() -> commands.Bot:
    """Construct a fully-wired discord.py Bot: shared core layer, shared
    tools, shared AI handler, all attached to the bot instance so every
    cog in discord_bot/ uses the same objects rather than each
    constructing its own.

    This mirrors main.py's role for the whole process, but scoped to
    just what the Discord adapter needs — main.py calls this once and
    runs the result; a future telegram_bot/client.py would have an
    analogous build_bot()/build_dispatcher() that's handed the SAME
    core.db/auth/memory instances (see main.py) rather than fresh ones,
    which is what actually makes cross-platform memory and identity work.
    """
    intents = discord.Intents.default()
    intents.message_content = True
    intents.members = True
    intents.guilds = True

    bot = commands.Bot(command_prefix="!", intents=intents)

    # NOTE: constructed here for now (Discord-only phase). Once a second
    # platform adapter exists, main.py should construct these ONCE and
    # pass them into build_bot(db=..., auth=..., memory=...) instead, so
    # both adapters share the same instances rather than each opening
    # its own sqlite connection pool to the same file. Fine as-is while
    # Discord is the only adapter running.
    bot.db = DatabaseManager()
    bot.auth = AuthManager(bot.db)
    bot.memory = MemoryManager(bot.db)
    bot.search_tool = SearchTool()
    bot.ai_handler = None  # set below, after coin_manager cog loads (see on_ready)

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

        # AIHandler needs the CoinManager cog, which only exists after
        # cogs are loaded — constructed here rather than in build_bot().
        coin_manager = bot.get_cog('CoinManager')
        bot.ai_handler = AIHandler(bot.db, bot.auth, bot.memory, coin_manager, bot.search_tool)

        await _sync_slash_commands(bot)

        search_tool_cog = bot.get_cog('SearchCommand')
        if search_tool_cog:
            await search_tool_cog.notify_admins_if_disabled()

    @bot.event
    async def on_message(message):
        if message.author == bot.user:
            return
        # discord.py automatically dispatches on_message to cog listeners
        # (message_listener.py's mention handling) without anything else
        # needed here.
        pass

    return bot


async def _load_cogs(bot: commands.Bot):
    cogs_list = [
        'discord_bot.auth_commands',
        'discord_bot.memory_commands',
        'discord_bot.coin_commands',
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


def run():
    """Build and run the Discord bot. Blocks until the bot disconnects.
    Called by main.py."""
    token = os.getenv('DISCORD_TOKEN')
    if not token:
        print("ERROR: DISCORD_TOKEN not found in environment variables!")
        return

    bot = build_bot()
    try:
        bot.run(token)
    except Exception as e:
        print(f"Error running Discord bot: {e}")
