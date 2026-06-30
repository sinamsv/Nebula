import discord
from discord.ext import commands
import os
from dotenv import load_dotenv
import asyncio

# Load environment variables
load_dotenv()

# Bot configuration
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True

# command_prefix is kept only because discord.py's commands.Bot requires one
# at construction time. No prefix ("!") commands are registered anymore —
# all user-facing commands are slash (app) commands, synced on startup.
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    """Called when the bot is ready."""
    print(f'{bot.user} has connected to Discord!')
    print(f'Bot is in {len(bot.guilds)} guilds')

    # Load all cogs
    await load_cogs()

    # Sync slash commands with Discord
    await sync_slash_commands()

async def load_cogs():
    """Load all cog modules."""
    cogs_list = [
        'cogs.memory_manager',
        'cogs.coin_manager',
        'cogs.ai_handler',
        'cogs.admin_tools',
        'cogs.search_tool',
    ]

    for cog in cogs_list:
        try:
            await bot.load_extension(cog)
            print(f'Loaded {cog}')
        except Exception as e:
            print(f'Failed to load {cog}: {e}')

async def sync_slash_commands():
    """Sync slash (app) commands with Discord.

    Global syncs can take up to an hour to propagate. For faster iteration
    during development, set DEV_GUILD_ID in .env to sync instantly to a
    single test server instead.
    """
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

@bot.event
async def on_message(message):
    """Pass incoming messages through to cog listeners (e.g. AIHandler's
    mention-based conversation handling in ai_handler.py).

    No prefix commands are processed here anymore since all commands
    are now slash commands handled directly by discord.py's app_commands
    dispatcher.
    """
    # Ignore bot's own messages
    if message.author == bot.user:
        return

    # discord.py automatically dispatches on_message to all cog listeners
    # (like AIHandler.on_message) without needing anything else here.
    pass

def main():
    """Main function to run the bot."""
    token = os.getenv('DISCORD_TOKEN')

    if not token:
        print("ERROR: DISCORD_TOKEN not found in environment variables!")
        return

    try:
        bot.run(token)
    except Exception as e:
        print(f"Error running bot: {e}")

if __name__ == "__main__":
    main()
