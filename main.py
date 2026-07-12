"""Nebula — top-level launcher.

This is the ONE file you run: `python main.py`.

Both platform adapters (Discord, Telegram) share a single set of
core.database/auth/memory/coins instances and a single
ai.handler.AIHandler, all constructed exactly once here. That sharing is
what makes identity, memory, and coin balance genuinely cross-platform:
a message sent via Telegram and a message sent via Discord for the SAME
Nebula account read and write through the exact same objects, not two
siloed copies of the same sqlite file. This replaces the previous
Discord-only setup where discord_bot.client.build_bot() constructed its
own db/auth/memory/search_tool internally — see that module's git
history / the version of this file before the Telegram adapter existed.

Each adapter is independently optional: whichever of DISCORD_TOKEN /
TELEGRAM_BOT_TOKEN is set in .env determines which adapter(s) actually
start. Both, one, or (if neither is set) neither — with an explicit
error in that last case rather than silently doing nothing, matching
this project's "explicit failure over silent fallback" principle
everywhere else (see core/auth.py, core/memory.py, tools/search.py).
"""
import asyncio
import os

from dotenv import load_dotenv

load_dotenv()

from core.database import DatabaseManager
from core.auth import AuthManager
from core.memory import MemoryManager
from core.coins import CoinManager
from tools.search import SearchTool
from ai.handler import AIHandler

import discord_bot.client as discord_client
import telegram_bot.client as telegram_client


async def main():
    db = DatabaseManager()
    auth = AuthManager(db)
    memory = MemoryManager(db)
    coins = CoinManager(db)
    search_tool = SearchTool()
    ai_handler = AIHandler(db, auth, memory, coins, search_tool)

    tasks = []

    discord_token = os.getenv('DISCORD_TOKEN')
    if discord_token:
        bot = discord_client.build_bot(db, auth, memory, coins, search_tool, ai_handler)
        tasks.append(discord_client.start(bot, discord_token))
        print("Discord adapter configured — starting.")
    else:
        print("DISCORD_TOKEN not set — Discord adapter disabled.")

    telegram_token = os.getenv('TELEGRAM_BOT_TOKEN')
    if telegram_token:
        application = telegram_client.build_application(
            db, auth, memory, coins, search_tool, ai_handler, telegram_token
        )
        tasks.append(telegram_client.start(application))
        print("Telegram adapter configured — starting.")
    else:
        print("TELEGRAM_BOT_TOKEN not set — Telegram adapter disabled.")

    if not tasks:
        print(
            "ERROR: No platform adapters are configured. Set DISCORD_TOKEN "
            "and/or TELEGRAM_BOT_TOKEN in your .env file — Nebula has "
            "nothing to run."
        )
        return

    await asyncio.gather(*tasks)


if __name__ == "__main__":
    asyncio.run(main())
