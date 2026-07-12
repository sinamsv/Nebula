"""The generic (non-command) message handler: hands off qualifying
Telegram messages to the platform-agnostic AI handler.

Two trigger conditions, deliberately mirroring
discord_bot/message_listener.py:
- Private chats: ANY text message triggers a response, no mention
  needed -- Telegram's native equivalent of a Discord DM (inherently
  1:1, no ambiguity about who a message is "for").
- Group chats: the bot's @username must appear in the message text,
  mirroring Discord's guild @mention requirement.

This module is deliberately thin: its only job is translating between
Telegram's Update/Context objects and the plain interface that
ai.handler.AIHandler.handle_turn() expects, then rendering the
TurnResult it gets back as actual Telegram messages. No identity/coin/
memory logic lives here -- all of that is inside ai/handler.py, shared
byte-for-byte with Discord.

Known gap: unlike discord_bot/message_listener.py, this handler does
not forward image attachments as a "[User attached N image(s)]" note.
Telegram's attachment model (PhotoSize arrays + file_id downloads) is
different enough from Discord's attachment URLs that this needed its
own implementation, which was out of scope for this pass -- left as a
follow-up.
"""
from telegram import Update
from telegram.constants import ChatAction, ChatType
from telegram.ext import Application, MessageHandler, filters, ContextTypes

TELEGRAM_PLATFORM = "telegram"
TELEGRAM_MESSAGE_LIMIT = 4096  # Telegram's per-message character limit (Discord's is 2000)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    chat = update.effective_chat
    user = update.effective_user

    if chat.type != ChatType.PRIVATE:
        # Group/supergroup: require an @mention, same gate as Discord
        # guild channels. Private chats skip this entirely (see module
        # docstring).
        bot_username = context.bot.username
        if not bot_username or f"@{bot_username}" not in (message.text or ""):
            return

    ai_handler = context.bot_data['ai_handler']

    user_content = message.text or ""
    if context.bot.username:
        # Safe no-op when there's no mention to strip (the private-chat
        # case), same reasoning as the Discord side.
        user_content = user_content.replace(f"@{context.bot.username}", "").strip()

    if message.reply_to_message and message.reply_to_message.text:
        replied_author = message.reply_to_message.from_user
        replied_name = (replied_author.first_name if replied_author else None) or "someone"
        user_content = (
            f"[Context - replying to message from {replied_name}]: "
            f"\"{message.reply_to_message.text}\"\n\n{user_content}"
        )

    display_name = user.first_name or user.username or str(user.id)

    # Single fire-and-expire (~5s) typing signal, sent once before the AI
    # call starts. Unlike Discord's typing() context manager, Telegram's
    # send_chat_action doesn't auto-refresh for the duration of a long
    # operation -- acceptable given typical response times, but a very
    # slow tool call could see the indicator disappear before the reply
    # arrives.
    await chat.send_chat_action(ChatAction.TYPING)

    result = await ai_handler.handle_turn(
        source_platform=TELEGRAM_PLATFORM,
        platform_user_id=str(user.id),
        display_name=display_name,
        message_text=user_content,
        # Telegram has no guild-moderation concept -- this automatically
        # excludes kick_user/ban_user/create_channel from the toolset,
        # see ai/handler.py's supports_guild_moderation.
        discord_guild=None,
    )

    if result.is_blocked:
        await _send_long_message(chat, result.blocked_reason)
        return

    for tool_message in result.tool_messages:
        await _send_long_message(chat, tool_message)

    if result.reply_text:
        await _send_long_message(chat, result.reply_text)

    if result.memory_warning:
        await _send_long_message(chat, result.memory_warning)


async def _send_long_message(chat, text: str):
    """Split and send long messages. Telegram's per-message limit (4096
    chars) differs from Discord's (2000), but the underlying lesson this
    project already learned applies just the same: apply this
    consistently to every send, or risk a silent truncation bug like the
    one that caused the original search-freeze issue."""
    if len(text) <= TELEGRAM_MESSAGE_LIMIT:
        await chat.send_message(text)
        return

    chunks = []
    current_chunk = ""
    for line in text.split('\n'):
        if len(current_chunk) + len(line) + 1 <= TELEGRAM_MESSAGE_LIMIT:
            current_chunk += line + '\n'
        else:
            if current_chunk:
                chunks.append(current_chunk.strip())
            current_chunk = line + '\n'
    if current_chunk:
        chunks.append(current_chunk.strip())

    for i, chunk in enumerate(chunks):
        if i > 0:
            chunk = f"(continued)\n{chunk}"
        await chat.send_message(chunk)


def register(application: Application):
    # TEXT & ~COMMAND: qualifying plain-text messages only. Without the
    # ~COMMAND exclusion, a message like "/coin" would ALSO be routed
    # here (in addition to its dedicated CommandHandler), sending it to
    # the AI as if it were a chat message.
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
