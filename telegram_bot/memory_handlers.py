"""The /memory_stats and /memory_reset Telegram commands, operating on
the CALLER's own memory only -- same not-admin-only, no-target-parameter
design as discord_bot/memory_commands.py, for the same reason: memory is
personal, cross-platform data belonging to the individual Nebula
account, not a shared server resource an admin should be able to wipe
for someone else through a command.
"""
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from core.auth import AuthError

TELEGRAM_PLATFORM = "telegram"


async def memory_stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    auth = context.bot_data['auth']
    memory = context.bot_data['memory']
    user = update.effective_user

    try:
        identity = auth.require_approved_identity(TELEGRAM_PLATFORM, str(user.id))
    except AuthError as e:
        await update.message.reply_text(str(e))
        return

    stats = memory.get_usage(identity['nebula_user_id'])
    full_note = "\n\nMemory full — run /memory_reset to keep chatting." if stats['is_full'] else ""

    await update.message.reply_text(
        f"💾 Your Nebula Memory Usage\n"
        f"Total tokens used: {stats['total_tokens']:,}\n"
        f"Tokens remaining: {stats['remaining']:,}\n"
        f"Usage percentage: {stats['percentage']}%\n"
        f"Maximum capacity: {stats['max_tokens']:,} tokens" + full_note
    )


async def memory_reset_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    auth = context.bot_data['auth']
    memory = context.bot_data['memory']
    user = update.effective_user

    try:
        identity = auth.require_approved_identity(TELEGRAM_PLATFORM, str(user.id))
    except AuthError as e:
        await update.message.reply_text(str(e))
        return

    memory.reset_memory(identity['nebula_user_id'])

    await update.message.reply_text(
        "🔄 Your Nebula conversation memory has been cleared. This affects "
        "every platform you've linked to this account, not just Telegram."
    )


def register(application: Application):
    application.add_handler(CommandHandler("memory_stats", memory_stats_command))
    application.add_handler(CommandHandler("memory_reset", memory_reset_command))
