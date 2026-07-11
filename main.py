"""Nebula — top-level launcher.

This is the ONE file you run: `python main.py`.

Today this only starts the Discord adapter (discord_bot.client.run()),
which internally constructs its own core.database/auth/memory instances
(see discord_bot/client.py's build_bot()). That's fine as a single-
adapter setup.

Once a second adapter is added (Telegram, or an API server), this file's
job changes: it should construct core.database.DatabaseManager,
core.auth.AuthManager, and core.memory.MemoryManager ONCE here, pass the
SAME instances into both discord_bot.client.build_bot(...) and e.g.
telegram_bot.client.build_dispatcher(...), and run both concurrently
with asyncio.gather(). Sharing one set of core instances (rather than
each adapter opening its own) is what makes identity and memory actually
cross-platform instead of two siloed copies of the same sqlite file.
Sketch of what that will look like:

    async def main():
        db = DatabaseManager()
        auth = AuthManager(db)
        memory = MemoryManager(db)

        discord_bot = discord_bot.client.build_bot(db, auth, memory)
        telegram_bot = telegram_bot.client.build_dispatcher(db, auth, memory)

        await asyncio.gather(
            discord_bot.start(os.getenv('DISCORD_TOKEN')),
            telegram_bot.start_polling(),
        )

For now, discord_bot.client.run() does the equivalent of the above but
scoped to just Discord, including its own token check and error
handling.
"""
from dotenv import load_dotenv

load_dotenv()

from discord_bot.client import run as run_discord


def main():
    # Only the Discord adapter exists today. When a Telegram adapter or
    # API server is added, this becomes an asyncio.gather() of all
    # enabled adapters instead of a single blocking call — see the
    # module docstring above for the shape that will take.
    run_discord()


if __name__ == "__main__":
    main()
