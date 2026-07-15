"""Platform-agnostic AI conversation handler.

This is the piece that used to be tangled inside cogs/ai_handler.py,
mixing OpenAI tool-calling logic with discord.Message handling. Now
split: this module knows nothing about Discord, Telegram, or any
specific platform. It takes plain values in and returns plain response
text out. discord_bot/message_listener.py (and telegram_bot's message
handler) are the thin pieces that know how to turn a platform-native
message object into a call to handle_turn() and how to send the
string(s) it returns back on that platform.

As of this version, this module also knows nothing about any specific
AI SDK. Previously it imported AsyncOpenAI directly and called OpenAI's
chat.completions API inline. That's been replaced with the
ai/providers/ abstraction (see ai/providers/base.py's BaseProvider):
this file resolves WHICH provider to construct (from AI_PROVIDER/
AI_API_KEY, or the deprecated OPENAI_API_KEY/OPENAI_BASE_URL pair) and
then only ever calls the provider through its two normalized methods,
call() and append_tool_round(). No SDK-specific type or shape appears
anywhere below this point.

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
from dataclasses import dataclass
from typing import Dict, List, Optional

from core.auth import AuthManager
from core.memory import MemoryManager
from core.database import DatabaseManager
from tools.search import SearchTool
from tools import moderation
from ai.providers.base import BaseProvider

CONFIG_PATH = os.path.join(os.path.dirname(__file__), 'config.json')

# Every provider name this project knows how to construct. Must match
# ai/config.json's top-level keys exactly -- see _load_provider_config().
KNOWN_PROVIDERS = ("openai", "anthropic", "google", "xai", "openrouter", "groq")

# Which provider names route through OpenAISDKProvider (no dedicated
# SDK of their own -- see ai/providers/openai_sdk.py's module docstring
# for why these three share one file with "openai" itself).
_OPENAI_COMPATIBLE_PROVIDERS = ("openai", "xai", "openrouter", "groq")


class TurnResult:
    def __init__(self):
        self.tool_messages: List[str] = []
        self.reply_text: Optional[str] = None
        self.memory_warning: Optional[str] = None
        self.blocked_reason: Optional[str] = None

    @property
    def is_blocked(self) -> bool:
        return self.blocked_reason is not None


@dataclass
class _ResolvedProviderConfig:
    """Internal result of resolving which provider to construct and
    with what credentials, from whichever of the new (AI_PROVIDER/
    AI_API_KEY) or deprecated (OPENAI_API_KEY/OPENAI_BASE_URL) env var
    pairs is actually set. Not exposed outside this module."""
    provider_name: str
    api_key: str
    base_url_override: Optional[str]  # None = use config.json's value (if any)


class _ProviderConfigError(Exception):
    """Raised internally by the resolution/construction functions below
    with a user-facing-safe-to-log message. Always caught inside
    __init__ -- never propagates out of AIHandler construction, so a
    misconfigured or missing AI provider never crashes the whole app
    (matches the pre-refactor _setup_openai()'s behavior of printing a
    warning and leaving self.openai_client as None rather than raising)."""
    pass


class AIHandler:
    """Owns the AI provider and system prompt, and orchestrates one
    conversational turn: identity/memory/coin checks, the model call,
    tool dispatch, and memory writes.

    One AIHandler instance is shared across all platform adapters in a
    process (constructed once in main.py), same as core.database/auth/
    memory/coins are shared. `coin_manager` here is a core.coins.CoinManager
    instance (or any object exposing the same check_and_spend/MESSAGE_COST/
    SEARCH_COST/insufficient_funds_message interface) — this module has
    never imported discord.py and doesn't need to know that CoinManager
    used to also be a discord.py Cog before it was extracted to core/.
    """

    # Safety cap on the tool-calling round-trip loop in handle_turn() --
    # see the comment there for what this prevents. Unchanged from the
    # pre-refactor version.
    MAX_TOOL_ROUNDS = 5

    def __init__(self, db: DatabaseManager, auth: AuthManager, memory: MemoryManager,
                 coin_manager, search_tool: SearchTool):
        self.db = db
        self.auth = auth
        self.memory = memory
        self.coin_manager = coin_manager
        self.search_tool = search_tool

        # self.provider stays None (rather than raising out of __init__)
        # if resolution/construction fails for ANY reason -- a missing
        # provider, a missing key, or an unknown provider name. Every
        # other part of the app (non-AI commands like /coin, /signup,
        # /login, moderation tools reached without going through the
        # model) must keep working even when the AI backend itself
        # isn't configured. See _unconfigured_detail for what the admin
        # sees about WHY.
        self.provider: Optional[BaseProvider] = None
        self._unconfigured_detail: Optional[str] = None
        self._setup_provider()

        self._load_system_prompt()

    # ------------------------------------------------------------------
    # Provider resolution + construction
    # ------------------------------------------------------------------

    def _setup_provider(self):
        try:
            resolved = self._resolve_provider_and_key()
            config = self._load_provider_config(resolved.provider_name)
            self.provider = self._construct_provider(resolved, config)
            print(f"AI provider configured: {resolved.provider_name} (model={os.getenv('AI_MODEL')})")
        except _ProviderConfigError as e:
            self._unconfigured_detail = str(e)
            print(f"WARNING: AI provider not configured — {e}")

    def _resolve_provider_and_key(self) -> _ResolvedProviderConfig:
        """Resolve AI_PROVIDER/AI_API_KEY (preferred) or fall back to
        the deprecated OPENAI_API_KEY/OPENAI_BASE_URL pair. Explicit
        failure over silent fallback, matching the rest of this
        project's error-handling philosophy (see core/auth.py,
        core/memory.py, tools/search.py): if the person has clearly
        started configuring the NEW style (either var set) but not
        finished, that's a specific, nameable error -- not a silent
        drop-through to legacy behavior they may not even know exists.
        """
        provider = os.getenv('AI_PROVIDER')
        api_key = os.getenv('AI_API_KEY')

        if provider or api_key:
            if not provider:
                raise _ProviderConfigError(
                    "AI_API_KEY is set but AI_PROVIDER is not. Set AI_PROVIDER "
                    f"to one of: {', '.join(KNOWN_PROVIDERS)}."
                )
            if not api_key:
                raise _ProviderConfigError(
                    f"AI_PROVIDER is set to '{provider}' but AI_API_KEY is "
                    "missing. Set AI_API_KEY in your .env file."
                )
            if provider not in KNOWN_PROVIDERS:
                raise _ProviderConfigError(
                    f"AI_PROVIDER is set to '{provider}', which is not a "
                    f"recognized provider. Valid values: {', '.join(KNOWN_PROVIDERS)}."
                )
            return _ResolvedProviderConfig(
                provider_name=provider, api_key=api_key, base_url_override=None
            )

        legacy_key = os.getenv('OPENAI_API_KEY')
        if legacy_key:
            print(
                "DEPRECATION WARNING: OPENAI_API_KEY/OPENAI_BASE_URL are "
                "deprecated in favor of AI_PROVIDER + AI_API_KEY, and may be "
                "removed in a future release. See .env.sample for the new "
                "variables."
            )
            # OPENAI_BASE_URL is deliberately still honored here, not just
            # accepted-and-ignored: this project's own documented setup
            # (.env.sample, README.md's "AI API Key (Gemini example)"
            # section) has people point OPENAI_BASE_URL at Gemini's
            # OpenAI-compatible endpoint. Dropping that override would
            # silently break that exact, currently-documented setup for
            # anyone who upgrades without also hand-editing
            # ai/config.json — which is precisely the kind of silent
            # breakage this project's error-handling principle exists to
            # avoid. Flagged to Sina as a point worth re-confirming (see
            # accompanying summary), but implemented as "still honored"
            # since undoing it silently seemed like the larger risk.
            legacy_base_url = os.getenv('OPENAI_BASE_URL')
            return _ResolvedProviderConfig(
                provider_name='openai', api_key=legacy_key,
                base_url_override=legacy_base_url or None,
            )

        raise _ProviderConfigError(
            "No AI provider is configured. Set AI_PROVIDER and AI_API_KEY "
            "in your .env file."
        )

    def _load_provider_config(self, provider_name: str) -> Dict:
        try:
            with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
                full_config = json.load(f)
        except FileNotFoundError:
            raise _ProviderConfigError(f"ai/config.json not found at {CONFIG_PATH}.")
        except json.JSONDecodeError as e:
            raise _ProviderConfigError(f"ai/config.json is not valid JSON: {e}")

        if provider_name not in full_config:
            raise _ProviderConfigError(
                f"ai/config.json has no entry for provider '{provider_name}'."
            )
        return full_config[provider_name]

    def _construct_provider(self, resolved: _ResolvedProviderConfig, config: Dict) -> BaseProvider:
        ai_model = os.getenv('AI_MODEL')
        if not ai_model:
            raise _ProviderConfigError("AI_MODEL is not set.")

        base_url = resolved.base_url_override or config.get('base_url')
        temperature = config.get('temperature', 0.7)
        thinking_level = config.get('thinking_level')

        # xai/openrouter/groq have no SDK default endpoint of their own
        # to fall back to -- unlike openai/anthropic/google, which can
        # legitimately have base_url=None (their SDKs know their own
        # default). Catching this here gives a specific, actionable
        # error instead of that request going to the wrong host (or
        # OpenAI's own default) with a key that host will reject.
        if resolved.provider_name in ("xai", "openrouter", "groq") and not base_url:
            raise _ProviderConfigError(
                f"Provider '{resolved.provider_name}' requires a base_url "
                f"but none is set in ai/config.json and none was overridden."
            )

        if resolved.provider_name in _OPENAI_COMPATIBLE_PROVIDERS:
            from ai.providers.openai_sdk import OpenAISDKProvider
            return OpenAISDKProvider(
                api_key=resolved.api_key, model=ai_model, base_url=base_url,
                temperature=temperature, thinking_level=thinking_level,
            )
        elif resolved.provider_name == "anthropic":
            from ai.providers.anthropic_sdk import AnthropicSDKProvider
            return AnthropicSDKProvider(
                api_key=resolved.api_key, model=ai_model, base_url=base_url,
                temperature=temperature, thinking_level=thinking_level,
            )
        elif resolved.provider_name == "google":
            from ai.providers.google_sdk import GoogleSDKProvider
            return GoogleSDKProvider(
                api_key=resolved.api_key, model=ai_model, base_url=base_url,
                temperature=temperature, thinking_level=thinking_level,
            )
        else:
            # Unreachable given _resolve_provider_and_key()'s validation
            # against KNOWN_PROVIDERS, but explicit failure over a
            # silent fall-through if KNOWN_PROVIDERS and this if/elif
            # chain ever drift out of sync with each other.
            raise _ProviderConfigError(f"No provider implementation wired up for '{resolved.provider_name}'.")

    def get_admin_notice_if_unconfigured(self) -> Optional[str]:
        """Stateless getter: always returns the same detailed message
        (or None if the provider IS configured), with no "already sent"
        tracking on this object. Each adapter (discord_bot/, telegram_bot/)
        keeps its own independent sent-once flag, the same shape as the
        existing discord_bot/search_command.py's
        SearchCommand._admin_notice_sent -- see that class for the
        pattern this mirrors. Keeping the flag out of AIHandler means
        neither platform's notification suppresses the other's; each
        has a fully separate admin audience."""
        if self.provider is not None:
            return None
        return (
            "⚠️ Nebula AI Configuration Error\n"
            f"{self._unconfigured_detail}\n\n"
            "Nebula will not respond to AI chat messages until this is fixed."
        )

    @staticmethod
    def user_facing_unconfigured_message() -> str:
        """Deliberately generic -- no env var names, no provider names,
        nothing implementation-specific. A regular Discord/Telegram user
        hitting this doesn't need (and would likely be confused by)
        configuration details; that detail goes to admins only, via
        get_admin_notice_if_unconfigured() above."""
        return "⚠️ Nebula's AI isn't configured yet. Please contact a Nebula admin."

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

    # ------------------------------------------------------------------
    # Tools
    # ------------------------------------------------------------------

    def get_available_tools(self, is_admin: bool, supports_guild_moderation: bool) -> List[Dict]:
        """Unchanged from the pre-refactor version -- still produces
        OpenAI function-calling format. Each provider's call() is
        responsible for translating this into its own SDK's tool
        schema (see ai/providers/anthropic_sdk.py's _to_anthropic_tool
        and ai/providers/google_sdk.py's _to_genai_tools)."""
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

    # ------------------------------------------------------------------
    # Turn handling
    # ------------------------------------------------------------------

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

        messages = list(conversation_history)
        messages.append({"role": "user", "content": f"[{display_name}]: {message_text}"})

        # NOTE (existing, pre-refactor behavior, deliberately preserved
        # as-is per explicit instruction not to change this without
        # asking): this check happens AFTER coins have already been
        # spent above. A user whose turn fails here because the AI
        # backend isn't configured still loses a coin for that turn.
        # This was true before this refactor too (the old
        # `if not self.openai_client:` check was in this same relative
        # position) -- not something this task changed, and not
        # something to silently "fix" as a side effect of this
        # refactor. Flagged again in the accompanying summary as
        # something to explicitly revisit with Sina if desired.
        if not self.provider:
            result.blocked_reason = self.user_facing_unconfigured_message()
            return result

        usage_after_user_msg = await self.memory.add_message_to_memory(
            nebula_user_id, "user", message_text, source_platform
        )

        # Bounded, provider-agnostic tool-calling loop. Shape unchanged
        # from the pre-refactor version (see MAX_TOOL_ROUNDS docstring
        # above and the bug this loop originally fixed), except that
        # every provider-specific detail (how to call the model, how to
        # append a tool round to the running message list) now goes
        # through self.provider's two normalized methods instead of
        # inline OpenAI-specific code. The loop itself has no idea
        # which SDK is behind self.provider.
        final_content = None
        tools = self.get_available_tools(is_admin, supports_guild_moderation)
        for _ in range(self.MAX_TOOL_ROUNDS):
            try:
                response = await self.provider.call(messages, tools, self.system_prompt)
            except Exception as e:
                print(f"Error calling AI backend: {e}")
                result.blocked_reason = f"Sorry {display_name}, I encountered an error processing your message. Please try again."
                return result

            if not response.has_tool_calls:
                final_content = response.content
                break

            tool_results = []
            for tool_call in response.tool_calls:
                tool_result = await self._execute_tool(
                    tool_call.name, tool_call.arguments, nebula_user_id, display_name,
                    identity, discord_guild
                )
                if tool_result:
                    result.tool_messages.append(tool_result)
                tool_results.append(tool_result)

            messages = self.provider.append_tool_round(messages, response, tool_results)
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
