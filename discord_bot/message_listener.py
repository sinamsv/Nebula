import discord
from discord.ext import commands

DISCORD_PLATFORM = "discord"


class MessageListener(commands.Cog):
    """Listens for messages that @mention the bot and hands them off to
    the platform-agnostic AI handler.

    This cog is deliberately thin: its only job is translating between
    discord.Message and the plain (text, display_name, nebula_user_id-
    resolving IDs) interface that ai.handler.AIHandler.handle_turn()
    expects, and then rendering the TurnResult it gets back as actual
    Discord messages. No identity/coin/memory logic lives here — all of
    that is inside ai/handler.py so a future Telegram message listener
    can call the exact same handle_turn() and get the exact same
    behavior.
    """

    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author == self.bot.user:
            return
        if not message.guild:
            return
        if self.bot.user not in message.mentions:
            return

        context_message = None
        if message.reference and message.reference.message_id:
            try:
                context_message = await message.channel.fetch_message(message.reference.message_id)
            except Exception:
                pass

        await self._handle_mention(message, context_message)

    async def _handle_mention(self, message: discord.Message, context_message: discord.Message = None):
        # ⚠️ این بخش و خطوط پایینش تو‌رفتی نداشتن که اصلاح شد
        ai_handler = self.bot.ai_handler
        if ai_handler is None:
            await message.channel.send(
                "⚠️ Nebula is still starting up. Please try again in a moment."
            )
            return

        user_content = message.content.replace(f'<@{self.bot.user.id}>', '').strip()

        if context_message:
            user_content = (
                f"[Context - replying to message from {context_message.author.display_name}]: "
                f"\"{context_message.content}\"\n\n{user_content}"
            )

        if message.attachments:
            image_urls = [
                att.url for att in message.attachments
                if att.content_type and att.content_type.startswith('image/')
            ]
            if image_urls:
                user_content += f"\n\n[User attached {len(image_urls)} image(s)]"

        # Typing indicator covers the whole "thinking" window: the model
        # call itself, plus any tool execution (e.g. a search request)
        # that happens inside handle_turn(). It stops the moment we exit
        # this block and start sending real messages.
        async with message.channel.typing():
            result = await ai_handler.handle_turn(
                source_platform=DISCORD_PLATFORM,
                platform_user_id=str(message.author.id),
                display_name=message.author.display_name,
                message_text=user_content,
                discord_guild=message.guild,
            )

        if result.is_blocked:
            await self._send_long_message(message.channel, result.blocked_reason)
            return

        # Tool output (e.g. search results) can exceed Discord's message
        # length limit just as easily as the model's own reply — route it
        # through the same chunking helper instead of a raw send().
        for tool_message in result.tool_messages:
            await self._send_long_message(message.channel, tool_message)

        if result.reply_text:
            await self._send_long_message(message.channel, result.reply_text)

        if result.memory_warning:
            await self._send_long_message(message.channel, result.memory_warning)

    async def _send_long_message(self, channel, text: str):
        """Split and send long messages (>2000 characters, Discord's limit)."""
        if len(text) <= 2000:
            await channel.send(text)
            return

        chunks = []
        current_chunk = ""
        for line in text.split('\n'):
            if len(current_chunk) + len(line) + 1 <= 2000:
                current_chunk += line + '\n'
            else:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = line + '\n'
        if current_chunk:
            chunks.append(current_chunk.strip())

        for i, chunk in enumerate(chunks):
            if i > 0:
                chunk = f"*(continued)*\n{chunk}"
            await channel.send(chunk)


async def setup(bot):
    """Setup function to load the cog."""
    await bot.add_cog(MessageListener(bot))
