"""Telegram adapter entry points.

build_application() constructs a fully-wired PTB Application around
instances built ONCE in main.py and shared with the Discord adapter --
same principle as discord_bot/client.py's build_bot(); see that
function's docstring for why sharing (rather than each adapter
constructing its own) is what makes identity/memory/coins genuinely
cross-platform.

start() runs the built Application under main.py's asyncio.gather()
without it managing its own event loop, mirroring discord_bot.client.start().
"""
import asyncio

from telegram.ext import Application, ApplicationBuilder

from core.database import DatabaseManager
from core.auth import AuthManager
from core.memory import MemoryManager
from core.coins import CoinManager
from tools.search import SearchTool
from ai.handler import AIHandler

from telegram_bot import auth_handlers, coin_handlers, memory_handlers, message_handler

TELEGRAM_PLATFORM = "telegram"

# Registered via Bot.set_my_commands so they show up in Telegram's own
# command-list UI -- the closest equivalent to how Discord surfaces
# slash-command descriptions. Purely cosmetic; doesn't affect routing
# (each CommandHandler is what actually wires a command to its handler).
_COMMAND_DESCRIPTIONS = [
    ("start", "Get started with Nebula"),
    ("signup", "Create a new Nebula account"),
    ("login", "Log in to an existing Nebula account"),
    ("verify", "Link this Telegram account using a /sync code from Discord"),
    ("coin", "Check your Nebula Coin balance"),
    ("add_coin", "[Admin] Add to or set a user's coin balance"),
    ("memory_stats", "Show your Nebula memory usage"),
    ("memory_reset", "Clear your Nebula conversation memory"),
]


def build_application(db: DatabaseManager, auth: AuthManager, memory: MemoryManager,
                       coin_manager: CoinManager, search_tool: SearchTool,
                       ai_handler: AIHandler, token: str) -> Application:
    """Unlike discord's build_bot(), the token is required here at
    construction time (ApplicationBuilder needs it to build the
    underlying Bot object), not just at start() -- a real asymmetry
    between the two libraries, not an inconsistency in this project's
    own design."""
    application = ApplicationBuilder().token(token).build()

    # bot_data is PTB's own recommended mechanism for making shared
    # dependencies available inside every handler without threading them
    # through as closures individually -- a plain persistent dict
    # attached to the Application. See telegram_bot/*_handlers.py's
    # context.bot_data[...] reads.
    application.bot_data['db'] = db
    application.bot_data['auth'] = auth
    application.bot_data['memory'] = memory
    application.bot_data['coin_manager'] = coin_manager
    application.bot_data['search_tool'] = search_tool
    application.bot_data['ai_handler'] = ai_handler

    auth_handlers.register(application)
    coin_handlers.register(application)
    memory_handlers.register(application)
    # Registered last: within a group, PTB dispatches an update to only
    # the first handler (in registration order) whose filter matches, so
    # keeping the generic catch-all message handler last is good
    # practice regardless of the ~filters.COMMAND exclusion it also
    # carries (see message_handler.py's register()).
    message_handler.register(application)

    return application


async def start(application: Application):
    """Async-friendly entry point for main.py's asyncio.gather().

    Application.run_polling() manages its own event loop internally
    (like discord.py's old bot.run()) and can't be used directly
    alongside another async framework sharing one loop. This manually
    replicates what run_polling() does under the hood -- initialize,
    start, start polling via the Updater, then block until cancelled --
    so it plays nicely with asyncio.gather() the same way
    discord_bot.client.start() does for the Discord side.
    """
    try:
        await application.bot.set_my_commands(_COMMAND_DESCRIPTIONS)
    except Exception as e:
        print(f"Failed to set Telegram command descriptions: {e}")

    await application.initialize()
    await application.start()
    await application.updater.start_polling()
    print("Telegram adapter connected and polling for updates.")

    try:
        # start_polling() runs in the background and returns immediately;
        # this coroutine needs to stay alive (not return) for as long as
        # the bot should keep running, or main.py's asyncio.gather()
        # would treat this adapter as "done" the moment it's awaited.
        await asyncio.Event().wait()
    finally:
        await application.updater.stop()
        await application.stop()
        await application.shutdown()
