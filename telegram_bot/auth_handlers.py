"""Telegram commands for account creation, login, and cross-platform
account linking.

Mirrors discord_bot/auth_commands.py in spirit -- thin translation
between Telegram's Update/Context objects and core.auth.AuthManager,
which is where all real validation, hashing, and bootstrap logic lives
(shared with Discord, not duplicated here). The one command with no
Discord equivalent is /verify, which is the consuming side of the
/sync flow started on Discord -- see discord_bot/sync_commands.py and
core/auth.py's generate_sync_code/verify_sync_code docstrings for the
full flow and why the direction is fixed (Discord issues, Telegram
consumes, not the reverse).
"""
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from core.auth import AuthError
from telegram_bot.utils import parse_labeled_args

TELEGRAM_PLATFORM = "telegram"

# Shown after any command that necessarily put a password in the chat's
# message history. Telegram bots cannot delete a user's OWN message in a
# private chat (only their own messages, and only as an admin in groups,
# which doesn't apply here) -- this warning is the only mitigation
# available, matching what was explicitly decided for this flow.
_PASSWORD_DELETE_WARNING = (
    "\n\n⚠️ For your security, please delete your previous message now — "
    "it contains your password in plain text, and I'm not able to delete "
    "it for you in a private chat."
)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Welcome to Nebula!\n\n"
        "If you already have a Nebula account (e.g. from Discord), link this "
        "Telegram account to it with /sync on Discord first, then come back "
        "here and use /verify with the code it gives you.\n\n"
        "If this is your first time, create an account directly here:\n"
        "/signup username:<name> password:<password>\n\n"
        "Already have an account and just want to log in from here?\n"
        "/login username:<name> password:<password>"
    )


async def signup_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    auth = context.bot_data['auth']
    user = update.effective_user

    args = parse_labeled_args(update.message.text, ['username', 'password', 'bootstrap_key'])
    username = args.get('username')
    password = args.get('password')
    bootstrap_key = args.get('bootstrap_key')

    if not username or not password:
        await update.message.reply_text(
            "Usage: /signup username:<name> password:<password>\n"
            "(Admin setup only: add bootstrap_key:<key> to claim the first admin account)"
        )
        return

    display_name = user.first_name or user.username or str(user.id)

    try:
        result = auth.signup(
            username=username, password=password, display_name=display_name,
            platform=TELEGRAM_PLATFORM, platform_user_id=str(user.id),
            platform_display_name=display_name, bootstrap_key=bootstrap_key,
        )
    except AuthError as e:
        await update.message.reply_text(str(e))
        return

    if result['became_admin']:
        await update.message.reply_text(
            f"✅ Account {result['username']} created and linked to your Telegram "
            f"identity.\n👑 You claimed the bootstrap key and are now Nebula's first "
            f"admin — approved automatically. Use /add_admin-equivalent commands on "
            f"Discord, or approve future signups from there, since admin management "
            f"commands are currently Discord-only." + _PASSWORD_DELETE_WARNING
        )
        return

    await update.message.reply_text(
        f"✅ Account {result['username']} created and linked to your Telegram "
        f"identity.\n⏳ Your account is pending approval from an admin before you "
        f"can chat with Nebula or use tools." + _PASSWORD_DELETE_WARNING
    )


async def login_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    auth = context.bot_data['auth']
    user = update.effective_user

    args = parse_labeled_args(update.message.text, ['username', 'password'])
    username = args.get('username')
    password = args.get('password')

    if not username or not password:
        await update.message.reply_text("Usage: /login username:<name> password:<password>")
        return

    display_name = user.first_name or user.username or str(user.id)

    try:
        result = auth.login(
            username=username, password=password, platform=TELEGRAM_PLATFORM,
            platform_user_id=str(user.id), platform_display_name=display_name,
        )
    except AuthError as e:
        await update.message.reply_text(str(e))
        return

    if not result['is_approved']:
        await update.message.reply_text(
            f"✅ Logged in as {result['username']} and linked to this Telegram "
            f"identity.\n⏳ Note: this account is still pending admin approval, so "
            f"Nebula won't respond to you yet." + _PASSWORD_DELETE_WARNING
        )
        return

    await update.message.reply_text(
        f"✅ Logged in as {result['username']} and linked to this Telegram identity. "
        f"Your memory and coin balance carry over from any other platform you've "
        f"used Nebula on." + _PASSWORD_DELETE_WARNING
    )


async def verify_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Consumes a sync code generated by Discord's /sync command. No
    password involved here (it's a short-lived, single-use code), so no
    delete-your-message warning is needed -- unlike /signup and /login."""
    auth = context.bot_data['auth']
    user = update.effective_user

    args = parse_labeled_args(update.message.text, ['username', 'code'])
    username = args.get('username')
    code = args.get('code')

    if not username or not code:
        await update.message.reply_text(
            "Usage: /verify username:<your Nebula username> code:<the code from /sync on Discord>"
        )
        return

    display_name = user.first_name or user.username or str(user.id)

    try:
        result = auth.verify_sync_code(
            username=username, code=code, target_platform=TELEGRAM_PLATFORM,
            platform_user_id=str(user.id), platform_display_name=display_name,
        )
    except AuthError as e:
        await update.message.reply_text(str(e))
        return

    approval_note = "" if result['is_approved'] else "\n⏳ Note: this account is still pending admin approval."
    await update.message.reply_text(
        f"✅ This Telegram account is now linked to Nebula account "
        f"{result['username']}. Your memory and coin balance carry over from "
        f"Discord (and any other platform you use)." + approval_note
    )


def register(application: Application):
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("signup", signup_command))
    application.add_handler(CommandHandler("login", login_command))
    application.add_handler(CommandHandler("verify", verify_command))
