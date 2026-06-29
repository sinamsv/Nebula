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

bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    """Called when the bot is ready."""
    print(f'{bot.user} has connected to Discord!')
    print(f'Bot is in {len(bot.guilds)} guilds')

    # Load all cogs
    await load_cogs()

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

@bot.event
async def on_message(message):
    """Handle incoming messages."""
    # Ignore bot's own messages
    if message.author == bot.user:
        return

    # Process commands first
    await bot.process_commands(message)

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
