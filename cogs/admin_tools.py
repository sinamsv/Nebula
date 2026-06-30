import discord
from discord import app_commands
from discord.ext import commands
from database import DatabaseManager
import re

class AdminTools(commands.Cog):
    """Admin tools for moderation and server management."""
    
    def __init__(self, bot):
        self.bot = bot
        self.db = DatabaseManager()
    
    def extract_user_id(self, user_mention: str) -> int:
        """Extract user ID from mention or ID string."""
        # Try to extract from mention format <@!123> or <@123>
        match = re.search(r'<@!?(\d+)>', user_mention)
        if match:
            return int(match.group(1))
        
        # Try to parse as direct ID
        try:
            return int(user_mention)
        except ValueError:
            return None
    
    async def kick_user_tool(self, message: discord.Message, user_mention: str, reason: str) -> str:
        """Tool function to kick a user."""
        # Verify admin permissions
        if not message.author.guild_permissions.administrator:
            return "❌ You don't have permission to kick users."
        
        # Extract user ID
        user_id = self.extract_user_id(user_mention)
        if not user_id:
            return f"❌ Could not identify user from: {user_mention}"
        
        try:
            # Get member
            member = await message.guild.fetch_member(user_id)
            
            if not member:
                return f"❌ Could not find user with ID: {user_id}"
            
            # Check if bot can kick this user
            if member.top_role >= message.guild.me.top_role:
                return f"❌ Cannot kick {member.display_name} - their role is higher than or equal to mine."
            
            # Kick the user
            await member.kick(reason=reason)
            
            # Log the action
            self.db.log_admin_action(
                str(message.guild.id),
                str(message.author.id),
                message.author.display_name,
                "kick",
                str(member.id),
                member.display_name,
                reason
            )
            
            return f"✅ Successfully kicked **{member.display_name}** (ID: {member.id})\nReason: {reason}"
        
        except discord.Forbidden:
            return "❌ I don't have permission to kick this user."
        except Exception as e:
            return f"❌ Error kicking user: {str(e)}"
    
    async def ban_user_tool(self, message: discord.Message, user_mention: str, reason: str) -> str:
        """Tool function to ban a user."""
        # Verify admin permissions
        if not message.author.guild_permissions.administrator:
            return "❌ You don't have permission to ban users."
        
        # Extract user ID
        user_id = self.extract_user_id(user_mention)
        if not user_id:
            return f"❌ Could not identify user from: {user_mention}"
        
        try:
            # Get member
            member = await message.guild.fetch_member(user_id)
            
            if not member:
                return f"❌ Could not find user with ID: {user_id}"
            
            # Check if bot can ban this user
            if member.top_role >= message.guild.me.top_role:
                return f"❌ Cannot ban {member.display_name} - their role is higher than or equal to mine."
            
            # Ban the user
            await member.ban(reason=reason, delete_message_days=0)
            
            # Log the action
            self.db.log_admin_action(
                str(message.guild.id),
                str(message.author.id),
                message.author.display_name,
                "ban",
                str(member.id),
                member.display_name,
                reason
            )
            
            return f"✅ Successfully banned **{member.display_name}** (ID: {member.id})\nReason: {reason}"
        
        except discord.Forbidden:
            return "❌ I don't have permission to ban this user."
        except Exception as e:
            return f"❌ Error banning user: {str(e)}"
    
    async def create_channel_tool(self, message: discord.Message, channel_name: str, 
                                 category_name: str = None, channel_type: str = "text") -> str:
        """Tool function to create a channel."""
        # Verify admin permissions
        if not message.author.guild_permissions.administrator:
            return "❌ You don't have permission to create channels."
        
        try:
            guild = message.guild
            category = None
            
            # Find category if specified
            if category_name:
                for cat in guild.categories:
                    if cat.name.lower() == category_name.lower():
                        category = cat
                        break
                
                if not category:
                    return f"❌ Could not find category: {category_name}"
            
            # Create channel
            if channel_type.lower() == "voice":
                channel = await guild.create_voice_channel(name=channel_name, category=category)
                channel_type_display = "voice"
            else:
                channel = await guild.create_text_channel(name=channel_name, category=category)
                channel_type_display = "text"
            
            # Log the action
            details = f"Created {channel_type_display} channel: {channel_name}"
            if category:
                details += f" in category: {category.name}"
            
            self.db.log_admin_action(
                str(message.guild.id),
                str(message.author.id),
                message.author.display_name,
                "create_channel",
                str(channel.id),
                channel_name,
                details
            )
            
            return f"✅ Successfully created {channel_type_display} channel: {channel.mention if channel_type_display == 'text' else channel.name}"
        
        except discord.Forbidden:
            return "❌ I don't have permission to create channels."
        except Exception as e:
            return f"❌ Error creating channel: {str(e)}"
    
    async def user_activity_tool(self, message: discord.Message, user_mention: str) -> str:
        """Tool function to check user activity."""
        # Verify admin permissions
        if not message.author.guild_permissions.administrator:
            return "❌ You don't have permission to check user activity."
        
        # Extract user ID
        user_id = self.extract_user_id(user_mention)
        if not user_id:
            return f"❌ Could not identify user from: {user_mention}"
        
        try:
            # Get user activity from database
            activity = self.db.get_user_activity(str(user_id), str(message.guild.id))
            
            if not activity:
                return f"❌ No activity data found for user ID: {user_id}"
            
            # Build response
            response = f"📊 **Activity Report for {activity['display_name']}**\n\n"
            response += f"👤 **User ID:** {user_id}\n"
            response += f"📅 **First Seen:** {activity['first_seen']}\n"
            response += f"🕐 **Last Seen:** {activity['last_seen']}\n"
            response += f"💬 **Total Messages:** {activity['total_messages']}\n"
            response += f"📈 **Messages (Last 7 Days):** {activity['messages_last_7_days']}\n"
            
            # Log the action
            self.db.log_admin_action(
                str(message.guild.id),
                str(message.author.id),
                message.author.display_name,
                "user_activity_check",
                str(user_id),
                activity['display_name'],
                "Checked user activity"
            )
            
            return response
        
        except Exception as e:
            return f"❌ Error checking user activity: {str(e)}"

    # ------------------------------------------------------------------
    # Slash Commands
    # ------------------------------------------------------------------

    @app_commands.command(name='admin_logs', description='[Admin] View recent admin action logs.')
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(limit='Number of log entries to show (max 50, default 10)')
    async def admin_logs(self, interaction: discord.Interaction, limit: int = 10):
        """View recent admin action logs."""
        if limit > 50:
            limit = 50
        elif limit < 1:
            limit = 1

        logs = self.db.get_admin_logs(str(interaction.guild.id), limit)

        if not logs:
            await interaction.response.send_message("No admin logs found.")
            return

        embed = discord.Embed(
            title="📋 Admin Action Logs",
            color=discord.Color.gold()
        )

        for i, log in enumerate(logs[:10], 1):
            value = f"**Action:** {log['action_type']}\n"
            if log['target_name']:
                value += f"**Target:** {log['target_name']}\n"
            if log['details']:
                value += f"**Details:** {log['details']}\n"
            value += f"**Time:** {log['timestamp']}"

            embed.add_field(
                name=f"{i}. {log['admin_name']}",
                value=value,
                inline=False
            )

        await interaction.response.send_message(embed=embed)

    @admin_logs.error
    async def admin_logs_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message("❌ Only administrators can use this command.", ephemeral=True)
        else:
            await interaction.response.send_message(f"❌ Error: {str(error)}", ephemeral=True)


async def setup(bot):
    """Setup function to load the cog."""
    await bot.add_cog(AdminTools(bot))
