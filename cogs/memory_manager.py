import discord
from discord import app_commands
from discord.ext import commands
from database import DatabaseManager
import tiktoken

class MemoryManager(commands.Cog):
    """Manages conversation memory and token tracking."""
    
    def __init__(self, bot):
        self.bot = bot
        self.db = DatabaseManager()
        self.max_tokens = 400000  # 400k token limit
        self.encoding = tiktoken.encoding_for_model("gpt-4")
    
    def count_tokens(self, text: str) -> int:
        """Count tokens in a text string."""
        try:
            return len(self.encoding.encode(text))
        except Exception as e:
            # Fallback: rough estimate
            return len(text) // 4
    
    async def add_message_to_memory(self, message: discord.Message, role: str, content: str):
        """Add a message to the conversation memory."""
        guild_id = str(message.guild.id)
        channel_id = str(message.channel.id)
        user_id = str(message.author.id)
        display_name = message.author.display_name
        
        # Count tokens
        token_count = self.count_tokens(content)
        
        # Check if we need to reset memory
        total_tokens = self.db.get_total_tokens(guild_id, channel_id)
        if total_tokens + token_count > self.max_tokens:
            print(f"Token limit reached ({total_tokens + token_count}), resetting conversation for channel {channel_id}")
            self.db.reset_conversation(guild_id, channel_id)
        
        # Add message to database
        self.db.add_message(guild_id, channel_id, user_id, display_name, role, content, token_count)
        
        # Update user profile
        self.db.update_user_profile(user_id, display_name, guild_id)
    
    def get_conversation_context(self, message: discord.Message, max_messages: int = 50):
        """Retrieve conversation context for AI processing."""
        guild_id = str(message.guild.id)
        channel_id = str(message.channel.id)
        
        history = self.db.get_conversation_history(guild_id, channel_id, max_messages)
        
        # Format for OpenAI API
        formatted_history = []
        for msg in history:
            formatted_history.append({
                "role": msg['role'],
                "content": f"[{msg['display_name']}]: {msg['content']}" if msg['role'] == 'user' else msg['content']
            })
        
        return formatted_history
    
    def get_token_usage(self, guild_id: str, channel_id: str) -> dict:
        """Get current token usage for a channel."""
        total_tokens = self.db.get_total_tokens(guild_id, channel_id)
        percentage = (total_tokens / self.max_tokens) * 100
        
        return {
            'total_tokens': total_tokens,
            'max_tokens': self.max_tokens,
            'percentage': round(percentage, 2),
            'remaining': self.max_tokens - total_tokens
        }

    # ------------------------------------------------------------------
    # Slash Commands
    # ------------------------------------------------------------------

    @app_commands.command(name='memory_stats', description='[Admin] Show memory usage statistics for this channel.')
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(administrator=True)
    async def memory_stats(self, interaction: discord.Interaction):
        """Show memory usage statistics for current channel."""
        guild_id = str(interaction.guild.id)
        channel_id = str(interaction.channel.id)

        stats = self.get_token_usage(guild_id, channel_id)

        embed = discord.Embed(
            title="💾 Memory Usage Statistics",
            color=discord.Color.blue()
        )
        embed.add_field(
            name="Total Tokens Used",
            value=f"{stats['total_tokens']:,}",
            inline=True
        )
        embed.add_field(
            name="Tokens Remaining",
            value=f"{stats['remaining']:,}",
            inline=True
        )
        embed.add_field(
            name="Usage Percentage",
            value=f"{stats['percentage']}%",
            inline=True
        )
        embed.add_field(
            name="Maximum Capacity",
            value=f"{stats['max_tokens']:,} tokens",
            inline=False
        )

        await interaction.response.send_message(embed=embed)

    @memory_stats.error
    async def memory_stats_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message("❌ Only administrators can use this command.", ephemeral=True)
        else:
            await interaction.response.send_message(f"❌ Error: {str(error)}", ephemeral=True)

    @app_commands.command(name='reset_memory', description='[Admin] Reset conversation memory for this channel.')
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(administrator=True)
    async def reset_memory(self, interaction: discord.Interaction):
        """Reset conversation memory for current channel."""
        guild_id = str(interaction.guild.id)
        channel_id = str(interaction.channel.id)

        self.db.reset_conversation(guild_id, channel_id)

        embed = discord.Embed(
            title="🔄 Memory Reset",
            description="Conversation memory has been reset for this channel.",
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=embed)

    @reset_memory.error
    async def reset_memory_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message("❌ Only administrators can use this command.", ephemeral=True)
        else:
            await interaction.response.send_message(f"❌ Error: {str(error)}", ephemeral=True)


async def setup(bot):
    """Setup function to load the cog."""
    await bot.add_cog(MemoryManager(bot))
