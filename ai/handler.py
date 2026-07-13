"""Platform-agnostic AI conversation handler.

This is the piece that used to be tangled inside cogs/ai_handler.py,
mixing OpenAI tool-calling logic with discord.Message handling. Now
split: this module knows nothing about Discord, Telegram, or any
specific platform. It takes plain values in and returns plain response
text out. discord_bot/message_listener.py (and telegram_bot's message
handler) are the thin pieces that know how to turn a platform-native
message object into a call to handle_turn() and how to send the
string(s) it returns back on that platform.

Tool execution has one unavoidable platform leak: kick_user, ban_user,
and create_channel operate on a discord.Guild (see tools/moderation.py's
docstring for why this can't be abstracted further without losing what
those actions do). handle_turn() accepts an optional `discord_guild`
parameter for exactly this — passed straight through to
tools/moderation.py without this module otherwise touching discord.py.
A platform that doesn't support guild moderation (Telegram, today)
simply never passes discord_guild, and the admin tool calls related to
it are omitted from the toolset (see get_available_tools).
"""
import json
import os
from typing import Dict, List, Optional

from openai import AsyncOpenAI

from core.auth import AuthManager
from core.memory import MemoryManager
from core.database import DatabaseManager
from tools.search import SearchTool
from tools import moderation


class TurnResult:
    def __init__(self):
        self.tool_messages: List[str] = []
        self.reply_text: Optional[str] = None
        self.memory_warning: Optional[str] = None
        self.blocked_reason: Optional[str] = None

    @property
    def is_blocked(self) -> bool:
        return self.blocked_reason is not None


class AIHandler:
    """Owns the OpenAI-compatible client and system prompt, and
    orchestrates one conversational turn: identity/memory/coin checks,
    the model call, tool dispatch, and memory writes.

    One AIHandler instance is shared across all platform adapters in a
    process (constructed once in main.py), same as core.database/auth/
    memory/coins are shared. `coin_manager` here is a core.coins.CoinManager
    instance (or any object exposing the same check_and_spend/MESSAGE_COST/
    SEARCH_COST/insufficient_funds_message interface) — this module has
    never imported discord.py and doesn't need to know that CoinManager
    used to also be a discord.py Cog before it was extracted to core/.
    """

    # Safety cap on the tool-calling round-trip loop in handle_turn() --
    # see the comment there for what this prevents.
    MAX_TOOL_ROUNDS = 5

    def __init__(self, db: DatabaseManager, auth: AuthManager, memory: MemoryManager,
                 coin_manager, search_tool: SearchTool):
        self.db = db
        self.auth = auth
        self.memory = memory
        self.coin_manager = coin_manager
        self.search_tool = search_tool

        self.openai_client = None
        self._setup_openai()
        self._load_system_prompt()

    def _setup_openai(self):
        api_key = os.getenv('OPENAI_API_KEY')
        base_url = os.getenv('OPENAI_BASE_URL')

        if not api_key:
            print("WARNING: OPENAI_API_KEY not found!")
            return

        if base_url:
            self.openai_client = AsyncOpenAI(api_key=api_key, base_url=base_url)
            print(f"Using custom OpenAI base URL: {base_url}")
        else:
            self.openai_client = AsyncOpenAI(api_key=api_key)
            print("Using default OpenAI endpoint")

    def _load_system_prompt(self):
        try:
            with open('system.txt', 'r', encoding='utf-8') as f:
                self.system_prompt = f.read().strip()
            print("System prompt loaded successfully")
        except FileNotFoundError:
            self.system_prompt = (
                "You are Nebula, a friendly and helpful AI assistant, available "
                "across multiple platforms. Your memory of a conversation follows "
                "the user's Nebula account, not any single platform."
            )
            print("WARNING: system.txt not found, using default system prompt")

    def get_available_tools(self, is_admin: bool, supports_guild_moderation: bool) -> List[Dict]:
        tools = [{
            "type": "function",
            "function": {
                "name": "search",
                "description": "Search the web for current information. Only use when user explicitly asks to search for something.",
                "parameters": {
                    "type": "object",
                    "properties": {"query": {"type": "string", "description": "The search query"}},
                    "required": ["query"]
                }
            }
        }]

        if is_admin and supports_guild_moderation:
            tools.extend([
                {
                    "type": "function",
                    "function": {
                        "name": "kick_user",
                        "description": "Kick a member from the server",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "user_mention": {"type": "string", "description": "The user mention (e.g., @username or user ID)"},
                                "reason": {"type": "string", "description": "Reason for kicking the user"}
                            },
                            "required": ["user_mention", "reason"]
                        }
                    }
                },
                {
                    "type": "function",
                    "function": {
                        "name": "ban_user",
                        "description": "Ban a member from the server",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "user_mention": {"type": "string", "description": "The user mention (e.g., @username or user ID)"},
                                "reason": {"type": "string", "description": "Reason for banning the user"}
                            },
                            "required": ["user_mention", "reason"]
                        }
                    }
                },
                {
                    "type": "function",
                    "function": {
                        "name": "create_channel",
                        "description": "Create a new channel in the server",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "channel_name": {"type": "string", "description": "Name of the channel to create"},
                                "category_name": {"type": "string", "description": "Name of the category to create channel in (optional)"},
                                "channel_type": {"type": "string", "enum": ["text", "voice"], "description": "Type of channel: text or voice"}
                            },
                            "required": ["channel_name", "channel_type"]
                        }
                    }
                },
                {
                    "type": "function",
                    "function": {
                        "name": "user_activity_check",
                        "description": "Check activity history of a specific user",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "user_mention": {"type": "string", "description": "The user mention (e.g., @username or user ID)"}
                            },
                            "required": ["user_mention"]
                        }
                    }
                }
            ])

        return tools

    async def handle_turn(
        self,
        *,
        source_platform: str,
        platform_user_id: str,
        display_name: str,
        message_text: str,
        discord_guild=None,
    ) -> TurnResult:
        result = TurnResult()

        try:
            identity = self.auth.require_approved_identity(source_platform, platform_user_id)
        except Exception as e:
            result.blocked_reason = str(e)
            return result

        nebula_user_id = identity['nebula_user_id']

        if self.memory.is_full(nebula_user_id):
            result.blocked_reason = self.memory.full_memory_message(display_name)
            return result

        if self.coin_manager:
            spend_result = self.coin_manager.check_and_spend(nebula_user_id, self.coin_manager.MESSAGE_COST)
            if not spend_result['success']:
                result.blocked_reason = self.coin_manager.insufficient_funds_message(
                    display_name, spend_result['seconds_until_reset']
                )
                return result

        conversation_history = self.memory.get_conversation_context(nebula_user_id)
        is_admin = identity['is_admin']
        supports_guild_moderation = discord_guild is not None

        messages = [{"role": "system", "content": self.system_prompt}]
        messages.extend(conversation_history)
        messages.append({"role": "user", "content": f"[{display_name}]: {message_text}"})

        if not self.openai_client:
            result.blocked_reason = "Sorry, the AI backend isn't configured right now."
            return result

        usage_after_user_msg = await self.memory.add_message_to_memory(
            nebula_user_id, "user", message_text, source_platform
        )

        # Bounded tool-calling loop. Bug fixed here: previously, after a
        # tool call was executed, the model was never called AGAIN with
        # the tool's output -- so it could never actually see or
        # synthesize a reply from what the tool returned. On a standard
        # tool-calling response, response_message.content is None (the
        # model hasn't produced a final answer yet, only a request to
        # call a tool), so the old code's `if response_message.content:`
        # check silently skipped storing ANY assistant reply for that
        # turn. Depending on the provider, either nothing got stored
        # (leaving a dangling, unanswered user turn in memory) or,
        # for providers that don't cleanly separate tool_calls from
        # content, whatever partial/premature text WAS present got
        # stored verbatim -- and then got replayed on every subsequent
        # turn, which is what produced the "repeats the search result
        # regardless of topic" symptom: a smaller model, weaker at
        # steering around unusual/malformed prior context, latched onto
        # that stored text and kept reproducing it.
        #
        # The fix: after executing a tool call, append the assistant's
        # tool-calling message (with its tool_calls field intact) plus a
        # matching role="tool" message per call, and ask the model AGAIN.
        # Capped at MAX_TOOL_ROUNDS so a model that keeps requesting
        # tools can't loop forever -- nothing in the current toolset
        # (search, kick, ban, create_channel, user_activity_check)
        # legitimately needs more than a couple of rounds in one turn.
        final_content = None
        for _ in range(self.MAX_TOOL_ROUNDS):
            try:
                response = await self._call_openai(messages, is_admin, supports_guild_moderation)
            except Exception as e:
                print(f"Error calling AI backend: {e}")
                result.blocked_reason = f"Sorry {display_name}, I encountered an error processing your message. Please try again."
                return result

            response_message = response.choices[0].message

            if not response_message.tool_calls:
                final_content = response_message.content
                break

            # Preserve the assistant's tool_calls message exactly as the
            # model sent it -- the follow-up role="tool" messages must
            # reference a tool_call_id that appeared in a preceding
            # assistant message, or the API will reject the next call.
            messages.append(response_message.model_dump(exclude_unset=True))

            for tool_call in response_message.tool_calls:
                function_name = tool_call.function.name
                function_args = json.loads(tool_call.function.arguments)
                tool_result = await self._execute_tool(
                    function_name, function_args, nebula_user_id, display_name,
                    identity, discord_guild
                )
                if tool_result:
                    result.tool_messages.append(tool_result)
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": tool_result or "(tool returned no output)",
                })
        # (no `else` needed: if the loop exhausts MAX_TOOL_ROUNDS without
        # ever hitting `break`, final_content simply stays None -- the
        # user still sees whatever tool_messages were collected along
        # the way, just without a final synthesized wrap-up on top.)

        if final_content:
            result.reply_text = final_content
            await self.memory.add_message_to_memory(
                nebula_user_id, "assistant", final_content, source_platform
            )

        result.memory_warning = self.memory.approaching_full_warning(usage_after_user_msg)
        return result

    async def _call_openai(self, messages: List[Dict], is_admin: bool, supports_guild_moderation: bool):
        tools = self.get_available_tools(is_admin, supports_guild_moderation)
        ai_model = os.getenv('AI_MODEL')
        return await self.openai_client.chat.completions.create(
            model=ai_model,
            messages=messages,
            tools=tools if tools else None,
            tool_choice="auto" if tools else None,
            temperature=0.7,
            max_tokens=2000
        )

    async def _execute_tool(self, function_name: str, function_args: Dict, nebula_user_id: int,
                             display_name: str, identity: Dict, discord_guild) -> Optional[str]:
        try:
            if function_name == "search":
                if self.coin_manager:
                    spend_result = self.coin_manager.check_and_spend(nebula_user_id, self.coin_manager.SEARCH_COST)
                    if not spend_result['success']:
                        return self.coin_manager.insufficient_funds_message(
                            display_name, spend_result['seconds_until_reset']
                        )
                return await self.search_tool.perform_search(function_args.get('query'))

            if discord_guild is None:
                return f"❌ Tool '{function_name}' is not available in this context."

            if function_name == "kick_user":
                return await moderation.kick_user(
                    self.db, discord_guild, display_name,
                    function_args.get('user_mention'), function_args.get('reason')
                )
            elif function_name == "ban_user":
                return await moderation.ban_user(
                    self.db, discord_guild, display_name,
                    function_args.get('user_mention'), function_args.get('reason')
                )
            elif function_name == "create_channel":
                return await moderation.create_channel(
                    self.db, discord_guild, display_name,
                    function_args.get('channel_name'),
                    function_args.get('category_name'),
                    function_args.get('channel_type')
                )
            elif function_name == "user_activity_check":
                return await moderation.check_user_activity(
                    self.db, self.memory, self.auth, display_name,
                    function_args.get('user_mention')
                )
            else:
                return f"Tool '{function_name}' not available or not implemented."

        except Exception as e:
            return f"Error executing tool '{function_name}': {str(e)}"
