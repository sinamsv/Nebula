"""Discord moderation tools: kick, ban, create_channel, and a Nebula-aware
user activity lookup.

Unlike tools/search.py, this module is NOT platform-agnostic — kick/ban/
create_channel are inherently Discord Guild API operations with no
Telegram equivalent, so there's no meaningful way to abstract them
further without losing what they actually do. What IS separated out is
the coupling to any specific Discord *command* — this module knows
nothing about slash commands, cogs, or discord.Message; it takes plain
discord.py domain objects (Guild, Member) and IDs.

Permission checking (is this caller a Nebula admin?) is deliberately NOT
done in this module. Callers — currently discord_bot/*_commands.py and
ai/handler.py — are responsible for checking admin status via
core.auth before calling any function here. This keeps "who is allowed"
(a core/auth concern) separate from "what the action does" (this
module's concern).
"""
import re
from typing import Optional

import discord

from core.database import DatabaseManager


def extract_discord_user_id(user_mention: str) -> Optional[int]:
    match = re.search(r'<@!?(\d+)>', user_mention)
    if match:
        return int(match.group(1))
    try:
        return int(user_mention)
    except ValueError:
        return None


async def kick_user(db: DatabaseManager, guild: discord.Guild, admin_display_name: str,
                     user_mention: str, reason: str) -> str:
    user_id = extract_discord_user_id(user_mention)
    if not user_id:
        return f"❌ Could not identify user from: {user_mention}"

    try:
        member = await guild.fetch_member(user_id)
        if not member:
            return f"❌ Could not find user with ID: {user_id}"

        if member.top_role >= guild.me.top_role:
            return f"❌ Cannot kick {member.display_name} - their role is higher than or equal to mine."

        await member.kick(reason=reason)
        db.log_admin_action(None, admin_display_name, "kick", None, member.display_name, reason)
        return f"✅ Successfully kicked **{member.display_name}** (ID: {member.id})\nReason: {reason}"

    except discord.Forbidden:
        return "❌ I don't have permission to kick this user."
    except Exception as e:
        return f"❌ Error kicking user: {str(e)}"


async def ban_user(db: DatabaseManager, guild: discord.Guild, admin_display_name: str,
                    user_mention: str, reason: str) -> str:
    user_id = extract_discord_user_id(user_mention)
    if not user_id:
        return f"❌ Could not identify user from: {user_mention}"

    try:
        member = await guild.fetch_member(user_id)
        if not member:
            return f"❌ Could not find user with ID: {user_id}"

        if member.top_role >= guild.me.top_role:
            return f"❌ Cannot ban {member.display_name} - their role is higher than or equal to mine."

        await member.ban(reason=reason, delete_message_days=0)
        db.log_admin_action(None, admin_display_name, "ban", None, member.display_name, reason)
        return f"✅ Successfully banned **{member.display_name}** (ID: {member.id})\nReason: {reason}"

    except discord.Forbidden:
        return "❌ I don't have permission to ban this user."
    except Exception as e:
        return f"❌ Error banning user: {str(e)}"


async def create_channel(db: DatabaseManager, guild: discord.Guild, admin_display_name: str,
                          channel_name: str, category_name: str = None,
                          channel_type: str = "text") -> str:
    try:
        category = None

        if category_name:
            for cat in guild.categories:
                if cat.name.lower() == category_name.lower():
                    category = cat
                    break
            if not category:
                return f"❌ Could not find category: {category_name}"

        if channel_type.lower() == "voice":
            channel = await guild.create_voice_channel(name=channel_name, category=category)
            channel_type_display = "voice"
        else:
            channel = await guild.create_text_channel(name=channel_name, category=category)
            channel_type_display = "text"

        details = f"Created {channel_type_display} channel: {channel_name}"
        if category:
            details += f" in category: {category.name}"

        db.log_admin_action(None, admin_display_name, "create_channel", None, channel_name, details)
        return f"✅ Successfully created {channel_type_display} channel: {channel.mention if channel_type_display == 'text' else channel.name}"

    except discord.Forbidden:
        return "❌ I don't have permission to create channels."
    except Exception as e:
        return f"❌ Error creating channel: {str(e)}"


async def check_user_activity(db: DatabaseManager, memory, auth, admin_display_name: str,
                               user_mention: str) -> str:
    user_id = extract_discord_user_id(user_mention)
    if not user_id:
        return f"❌ Could not identify user from: {user_mention}"

    identity = auth.resolve_identity("discord", str(user_id))
    if not identity:
        return f"❌ <@{user_id}> has no linked Nebula account."

    usage = memory.get_usage(identity['nebula_user_id'])

    response = f"📊 **Activity Report for {identity['display_name']}**\n\n"
    response += f"👤 **Nebula Username:** {identity['username']}\n"
    response += f"✅ **Approved:** {'Yes' if identity['is_approved'] else 'No'}\n"
    response += f"👑 **Admin:** {'Yes' if identity['is_admin'] else 'No'}\n"
    response += f"💾 **Memory Usage:** {usage['total_tokens']:,} / {usage['max_tokens']:,} tokens ({usage['percentage']}%)\n"

    db.log_admin_action(
        None, admin_display_name, "user_activity_check",
        identity['nebula_user_id'], identity['display_name'], "Checked user activity"
    )

    return response
