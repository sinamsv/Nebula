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


async def _notify_admins_if_ai_unconfigured(application: Application, db: DatabaseManager,
                                             ai_handler: AIHandler):
    """Unlike discord_bot/client.py's equivalent, this uses a direct
    database lookup (DatabaseManager.list_admin_platform_identities)
    rather than iterating any container of "known chats" -- Telegram has
    no "shared server" precondition for DMing a user the way Discord
    does. Any admin who has ever linked their Telegram identity (which
    requires having sent the bot at least one command already, since
    that's how linking happens in the first place -- see
    telegram_bot/auth_handlers.py) can be messaged directly by chat_id,
    with no need to first discover them via a shared group/channel.

    Runs once, after polling has started (so send calls have a live
    connection to work with) -- called from start() below, not
    build_application(), since build_application() only constructs the
    Application and doesn't yet have a running bot connection to send
    through.
    """
    notice = ai_handler.get_admin_notice_if_unconfigured()
    if notice is None:
        return

    admins = db.list_admin_platform_identities(TELEGRAM_PLATFORM)
    for admin in admins:
        try:
            await application.bot.send_message(chat_id=admin['platform_user_id'], text=notice)
        except Exception as e:
            name = admin['platform_display_name'] or admin['display_name']
            print(f"Failed to message admin {name} about AI misconfiguration: {e}")


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

    # Runs once per start() call (i.e. once per process run, not
    # per-reconnect the way discord_bot/client.py's on_ready-triggered
    # version can technically re-fire on a Discord reconnect) -- PTB's
    # start_polling() itself handles reconnects internally without
    # re-invoking start(), so no extra "already sent" guard is needed
    # here the way discord_bot/client.py needs bot._ai_admin_notice_sent
    # for its on_ready-triggered version.
    db = application.bot_data['db']
    ai_handler = application.bot_data['ai_handler']
    await _notify_admins_if_ai_unconfigured(application, db, ai_handler)

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
