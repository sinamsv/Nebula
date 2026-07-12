"""The /coin and /add_coin Telegram commands.

Same relationship to core.coins.CoinManager as discord_bot/coin_commands.py
has -- both are thin platform-specific wrappers around the one shared
business-logic object. See core/coins.py's docstring for why that
extraction happened.
"""
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from core.auth import AuthError
from core.coins import format_seconds
from telegram_bot.utils import parse_labeled_args

TELEGRAM_PLATFORM = "telegram"


async def coin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    auth = context.bot_data['auth']
    coins = context.bot_data['coin_manager']
    user = update.effective_user

    try:
        identity = auth.require_approved_identity(TELEGRAM_PLATFORM, str(user.id))
    except AuthError as e:
        await update.message.reply_text(str(e))
        return

    status = coins.get_status(identity['nebula_user_id'])
    await update.message.reply_text(
        f"🌝 Nebula Coin\n"
        f"Current balance: {status['balance']} coins\n"
        f"Time until reset: {format_seconds(status['seconds_until_reset'])}\n\n"
        f"Each message costs {coins.MESSAGE_COST} coin, each search costs "
        f"{coins.SEARCH_COST} coins, and each image costs {coins.IMAGE_COST} coins. "
        f"Balance is shared across every platform linked to your account."
    )


async def add_coin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = context.bot_data['db']
    auth = context.bot_data['auth']
    coins = context.bot_data['coin_manager']
    user = update.effective_user

    admin_identity = auth.resolve_identity(TELEGRAM_PLATFORM, str(user.id))
    if admin_identity is None or not admin_identity['is_approved']:
        await update.message.reply_text("❌ You need an approved Nebula account to do that.")
        return
    if not admin_identity['is_admin']:
        await update.message.reply_text("❌ Only Nebula admins can do that.")
        return

    args = parse_labeled_args(update.message.text, ['username', 'amount', 'mode'])
    username = args.get('username')
    amount_raw = args.get('amount')
    mode = args.get('mode', 'add')

    if not username or amount_raw is None:
        await update.message.reply_text(
            "Usage: /add_coin username:<name> amount:<number> mode:<add|set>\n"
            "(mode defaults to add if omitted)"
        )
        return

    if mode not in ('add', 'set'):
        await update.message.reply_text("❌ mode must be 'add' or 'set'.")
        return

    try:
        amount = int(amount_raw)
    except ValueError:
        await update.message.reply_text("❌ amount must be a whole number.")
        return

    target = db.get_user_by_username(username)
    if not target:
        await update.message.reply_text(f"❌ No Nebula account found with username {username}.")
        return

    new_balance = coins.modify_coins(target['nebula_user_id'], amount, mode)

    db.log_admin_action(
        admin_identity['nebula_user_id'],
        user.first_name or admin_identity['username'],
        "add_coin", target['nebula_user_id'], target['display_name'],
        f"mode={mode}, amount={amount}, new_balance={new_balance}"
    )

    verb = "added to" if mode == "add" else "set for"
    await update.message.reply_text(
        f"✅ Coins {verb} {target['display_name']} ({username}). New balance: {new_balance} coins."
    )


def register(application: Application):
    application.add_handler(CommandHandler("coin", coin_command))
    application.add_handler(CommandHandler("add_coin", add_coin_command))
