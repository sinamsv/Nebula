# Nebula - Detailed Documentation

> This file previously described an older `bot.py` + `cogs/` architecture with guild-scoped memory and coins, which predates the current per-account, multi-platform design. It's been updated below to match what's actually in the repository. If you're looking for the old prefix-command / per-guild behavior, see MIGRATION_GUIDE.md's version history.

## Table of Contents
1. [Architecture Overview](#architecture-overview)
2. [Identity & Multi-Platform Accounts](#identity--multi-platform-accounts)
3. [AI System](#ai-system)
4. [Memory Management](#memory-management)
5. [Nebula Coin System](#nebula-coin-system)
6. [Admin Tools](#admin-tools)
7. [Search Functionality](#search-functionality)
8. [Database Structure](#database-structure)
9. [Best Practices](#best-practices)

## Architecture Overview

Nebula splits cleanly into platform-agnostic business logic and thin, per-platform adapters:

```
main.py
  │  constructs ONE shared set of instances, passed into every adapter:
  ├── core.database.DatabaseManager
  ├── core.auth.AuthManager
  ├── core.memory.MemoryManager
  ├── core.coins.CoinManager
  ├── tools.search.SearchTool
  └── ai.handler.AIHandler
       │    (internally resolves + constructs one ai.providers.base.BaseProvider
       │     implementation — see "AI Provider Abstraction" below)
       │
       ├── discord_bot/  (adapter: translates discord.Message <-> handle_turn())
       └── telegram_bot/ (adapter: translates telegram.Update <-> handle_turn())
```

The reason this split exists: `ai/handler.py` has zero platform-specific imports (no `discord.py`, no `python-telegram-bot`). It takes plain strings in (`source_platform`, `platform_user_id`, `display_name`, `message_text`) and returns a plain `TurnResult` out. Each adapter's job is entirely translation — turning a platform-native message object into that plain call, and rendering the result back as platform-native messages. This is what let Telegram support get added without touching a single line of `ai/handler.py`, `core/auth.py`'s identity logic, or `core/memory.py`.

The same principle now applies one level deeper: `ai/handler.py` itself has zero AI-SDK-specific imports (no `openai`, `anthropic`, or `google.genai` types anywhere in that file). It talks only to an `ai.providers.base.BaseProvider` instance through two methods, `call()` and `append_tool_round()` — see "AI Provider Abstraction" below. This is what lets a new AI backend get added without touching `ai/handler.py`'s tool-calling loop, memory integration, or coin-spending logic.

The one deliberate exception (at the platform-adapter layer) is guild moderation (kick/ban/create_channel): these are inherently Discord Guild API operations with no Telegram equivalent, so `handle_turn()` accepts an optional `discord_guild` parameter that Telegram's adapter simply never passes, which automatically excludes those tools from what the AI model is offered.

### Component Responsibilities

- **main.py**: constructs every shared instance once, starts every adapter with a configured token via `asyncio.gather()`.
- **core/database.py**: SQLite abstraction for every table (accounts, platform links, sync codes, memory, coins, admin log).
- **core/auth.py**: signup/login/approval, plus the `/sync` → `/verify` cross-platform linking flow.
- **core/memory.py**: per-account conversation memory and the 200k-token cap.
- **core/coins.py**: Nebula Coin balance, spend, and reset logic.
- **ai/handler.py**: one conversational turn end-to-end — identity/memory/coin gating, AI provider resolution, the model call, tool dispatch, memory writes.
- **ai/providers/**: one file per AI SDK (`openai_sdk.py` covers OpenAI + xAI + OpenRouter + Groq, `anthropic_sdk.py`, `google_sdk.py`), each normalizing its SDK's request/response shape behind `base.py`'s `BaseProvider` interface.
- **tools/search.py**: web search (Google or Tavily), platform-agnostic.
- **tools/moderation.py**: kick/ban/create_channel/user-activity-check — Discord-only, takes plain `discord.py` objects.
- **discord_bot/**, **telegram_bot/**: thin adapters, one file per concern (auth, coins, memory, the AI message handler), mirroring each other's structure.

## Identity & Multi-Platform Accounts

A **Nebula account** (`nebula_users` table) is the actual unit everything hangs off of — memory, coin balance, and admin status all belong to a `nebula_user_id`, never to a Discord guild or a Telegram chat. A platform identity (a specific Discord user ID or Telegram user ID) is linked to a Nebula account via `platform_identities`; one account can have several platform identities linked to it (that's the whole point).

Two ways to end up with a platform identity linked to an account:
- **`/signup`** on either platform creates a brand-new account and links the calling platform identity to it immediately.
- **`/login`** links the calling platform identity to an *existing* account, after verifying the username/password.
- **`/sync` (Discord) + `/verify` (Telegram)** links a *new* platform identity to an *existing* account without re-entering a password on the new platform — instead, a one-time code generated on Discord is carried over and consumed on Telegram. See `core/auth.py`'s `generate_sync_code`/`verify_sync_code` for the full mechanics, and why the direction is fixed (Discord issues, Telegram consumes — Telegram won't let a bot message a user who hasn't messaged it first, so the reverse direction isn't available).

Unapproved accounts are not treated as if they don't exist — every gated action gives a specific "pending approval" message, not a generic failure, so a legitimate user always understands what to do next.

## AI System

### AI Provider Abstraction

`ai/handler.py` doesn't call any AI SDK directly. Instead, on construction it resolves which provider to use (from `AI_PROVIDER`/`AI_API_KEY`, or the deprecated `OPENAI_API_KEY`/`OPENAI_BASE_URL` pair — see "Provider Resolution" below) and constructs exactly one `ai.providers.base.BaseProvider` implementation:

```python
class BaseProvider(ABC):
    async def call(self, messages, tools, system_prompt) -> NormalizedResponse: ...
    def append_tool_round(self, messages, response, tool_results) -> list: ...
```

- **`call()`** sends one request to the provider's API and returns a `NormalizedResponse` — a `content` string (or `None`, if the model only requested tools) plus a list of `NormalizedToolCall` objects (`id`, `name`, `arguments` — already parsed into a dict regardless of provider).
- **`append_tool_round()`** takes the messages sent, the response received, and the plain-string result of executing each tool call, and returns the new message list to send on the next round. This is where each provider's own conversation-history format lives — OpenAI's `role="assistant"` + `role="tool"` messages, Anthropic's `tool_use`/`tool_result` content blocks, and Google's `Content(role="model"/"user", parts=[...])` shapes are all incompatible with each other, so each provider file owns its own translation rather than forcing them through one shared function in `ai/handler.py`.

Three provider files implement this:
- **`ai/providers/openai_sdk.py`**: covers `openai`, `xai`, `openrouter`, and `groq` — all four are the same `AsyncOpenAI` client pointed at a different `base_url`, with no SDK-specific behavior to branch on.
- **`ai/providers/anthropic_sdk.py`**: the official `anthropic` SDK. Handles the `thinking_level` → `budget_tokens` translation (see below).
- **`ai/providers/google_sdk.py`**: the official `google-genai` SDK (the current unified package — not the older `google-generativeai`).

`ai/handler.py`'s tool-calling loop (`MAX_TOOL_ROUNDS = 5`, unchanged from the pre-provider-abstraction version) only ever calls these two methods; it has no branch anywhere that checks which provider is active.

### Provider Configuration (`ai/config.json`)

Per-provider settings — `base_url` (override; `null` uses the SDK's own default where one exists), `temperature`, and `thinking_level` (`"low"`, `"medium"`, `"high"`, or `null` to disable extended thinking/reasoning):

```json
{
  "openai": { "base_url": null, "temperature": 0.7, "thinking_level": null },
  "anthropic": { "base_url": null, "temperature": 0.7, "thinking_level": null },
  "google": { "base_url": null, "temperature": 0.7, "thinking_level": null },
  "xai": { "base_url": "https://api.x.ai/v1", "temperature": 0.7, "thinking_level": null },
  "openrouter": { "base_url": "https://openrouter.ai/api/v1", "temperature": 0.7, "thinking_level": null },
  "groq": { "base_url": "https://api.groq.com/openai/v1", "temperature": 0.7, "thinking_level": null }
}
```

`xai`, `openrouter`, and `groq` require a `base_url` (they have no SDK default to fall back to); `openai`, `anthropic`, and `google` leave it `null` unless you're overriding the endpoint (e.g. a proxy or self-hosted gateway).

**`thinking_level` is a word, not a number**, and each provider translates it differently:
- OpenAI-family (`openai`/`xai`/`openrouter`/`groq`): passed straight through as `reasoning_effort` — these APIs already accept these same words natively.
- `anthropic`: translated to a numeric `budget_tokens` — `"low"` → 4000, `"medium"` → 10000, `"high"` → 24000 — since Anthropic's API takes a token budget, not a level word.
- `google`: passed as Gemini's own `ThinkingLevel` enum (`LOW`/`MEDIUM`/`HIGH`), which happens to already use the same three words. Note: Gemini also has an older, purely numeric `thinking_budget` mechanism (for Gemini 2.5-generation models); the two are mutually exclusive per Google's API, and this provider always uses `thinking_level`, matching Google's current guidance for 3.x+ models. Whether a given `AI_MODEL` string actually supports `thinking_level` depends on which model generation it is — this isn't validated in advance, the same way OpenAI's `reasoning_effort` isn't validated against whether the selected model supports it either.

### Provider Resolution

On construction, `ai/handler.py` resolves credentials in this order:
1. If `AI_PROVIDER` or `AI_API_KEY` is set, both must be set (an explicit error otherwise — not a silent fallback to legacy behavior), and `AI_PROVIDER` must be one of `openai`/`anthropic`/`google`/`xai`/`openrouter`/`groq`.
2. Otherwise, if the deprecated `OPENAI_API_KEY` is set, it's used with `provider=openai`, and `OPENAI_BASE_URL` (if set) still overrides `ai/config.json`'s `openai.base_url` — this keeps existing setups that point `OPENAI_BASE_URL` at a Gemini-compatible endpoint (or any other OpenAI-compatible proxy) working unchanged. A deprecation warning is printed to the console when this path is used.
3. Otherwise, the AI backend is left unconfigured.

**Unconfigured is not a crash.** If provider resolution fails for any reason (nothing set, an incomplete new-style config, or an unrecognized `AI_PROVIDER` value), `AIHandler.__init__` catches it internally — `self.provider` stays `None`, and every non-AI feature (`/coin`, `/signup`, `/login`, moderation tools reached without going through the model, etc.) keeps working normally. Two separate messages exist for this state:
- **User-facing** (`AIHandler.user_facing_unconfigured_message()`): a short, generic message with no configuration details — shown as the `blocked_reason` on `TurnResult` when someone tries to chat with Nebula while it's unconfigured.
- **Admin-facing** (`AIHandler.get_admin_notice_if_unconfigured()`): the specific reason (which env var, which problem), sent to admins on startup — printed to the console immediately, then DMed once to every linked Discord admin (via `discord_bot/client.py`'s `_notify_admins_if_ai_unconfigured`, which iterates guild members the same way `discord_bot/search_command.py`'s existing disabled-search notice does, since Discord bots can only DM someone they share a guild with) and messaged once to every linked Telegram admin (via `telegram_bot/client.py`'s equivalent, which — unlike Discord — looks admins up directly via `DatabaseManager.list_admin_platform_identities()`, since Telegram has no shared-server precondition for DMing a user). Each adapter tracks its own "already notified" state independently; neither platform starting first suppresses the other's notification.

**Known pre-existing behavior, unchanged by this refactor**: the coin-spend check happens before the provider-configured check in `handle_turn()` — a user whose turn fails because the AI backend isn't configured still loses a coin for that turn, same as before this refactor. This wasn't changed as part of adding the provider abstraction (see MIGRATION_GUIDE.md's "coins spent on a mis-configured turn" note if this behavior is ever revisited).

### Message Processing Flow (both platforms)

1. **Trigger check** (adapter-specific): Discord requires a mention in guild channels, none in DMs; Telegram requires a mention in groups, none in private chats.
2. **`ai.handler.AIHandler.handle_turn()`** — identical on both platforms from here on:
   - Resolve approved identity (or return a specific blocked reason).
   - Check memory isn't full.
   - Spend 1 coin (or return an insufficient-funds message).
   - Check the AI provider is configured (or return the generic unconfigured message).
   - Load conversation context (cross-platform, per-account).
   - Call the model, through the resolved provider, with the tools available to this identity/context.
   - Dispatch any tool calls.
   - Write both the user's message and the assistant's reply to memory.
3. **Adapter renders the result** back as platform-native messages, chunked to that platform's character limit (2000 for Discord, 4096 for Telegram).

### Tool System

Tools are defined in OpenAI's function-calling format (unchanged by the provider abstraction — every provider translates this same format into its own SDK's tool schema internally). Which tools are offered depends on the caller's admin status AND whether the platform passed a `discord_guild` (only Discord ever does):

```python
{
    "type": "function",
    "function": {
        "name": "tool_name",
        "description": "What the tool does",
        "parameters": { ... }
    }
}
```

`search` is always available to approved users. `kick_user`, `ban_user`, `create_channel`, `user_activity_check` are only offered when `is_admin` AND `discord_guild is not None` — i.e., never on Telegram.

### Context Window Management

- History retrieval: last 50 messages by default, per account, across every platform they've used.
- Token counting: `tiktoken`.
- Hard cap at 200,000 tokens (see Memory Management) — no automatic truncation or silent reset.

## Memory Management

### Token Tracking

```python
def count_tokens(self, text: str) -> int:
    return len(self.encoding.encode(text))
```

### Memory Lifecycle

1. Message arrives → tokens counted.
2. If already at/over the cap → the turn is refused *before* calling the model, with a message pointing to `/memory_reset`.
3. Otherwise the turn proceeds normally, and both the user's message and the assistant's reply are stored.
4. At 90%+ capacity (but not yet full), a soft warning is appended to an otherwise-normal response.

This is a **hard cap, not an auto-reset** — a deliberate change from an earlier version of this project that silently wiped history on overflow. Silently erasing someone's cross-platform memory without them asking for it is a worse surprise than telling them it's full.

### Memory Commands (any approved user, own memory only)

- `/memory_stats`: current token usage and percentage of capacity used.
- `/memory_reset`: clear conversation history for your account — affects every platform you're linked to, not just the one you ran it from.

## Nebula Coin System

- **Starting Balance**: 10 coins, per Nebula account (not per guild/chat).
- **Message Cost**: 1 coin. **Search Cost**: 2 coins.
- **Reset**: every 8 hours since the last reset, non-stacking (resets *to* 10, doesn't add 10).
- `/coin`: check your balance and time to reset.
- `/add_coin` (Discord, admin-only): add to or set a user's balance by Nebula username.

All of this logic lives in `core/coins.py`, shared verbatim between `ai/handler.py`'s per-turn spending, Discord's `/coin`/`/add_coin`, and Telegram's `/coin`/`/add_coin` — nothing is duplicated between platforms.

## Admin Tools

Admin status is a property of the Nebula account (`is_admin` on `nebula_users`), not any platform's own role/permission system.

### User Moderation (AI-Powered, Discord Only)

```
@Nebula kick @username reason here
@Nebula ban @username reason here
@Nebula create a text channel called "new-channel" in "Category Name"
@Nebula check activity for @username
```

`user_activity_check` reports the target's status across **every** platform they're linked to, not just the current Discord server — it's Nebula-aware, not purely Discord-aware, even though it's triggered from Discord and looks up the target via a Discord mention.

### Account Approval (Discord Only, for now)

- `/pending_users`: list accounts awaiting approval.
- `/approve_user username:<n> approve:<true|false>`: approve or reject.
- `/add_admin username:<n>`: promote an existing account to admin (auto-approves them too, if not already).

Reviewing signups that came in via Telegram's `/signup` still happens through these Discord commands — approval isn't currently exposed on Telegram itself.

### Admin Logging

Every admin action (from either platform) is logged to `admin_actions_log`. View with `/admin_logs [limit]` on Discord.

## Search Functionality

- **AI Tool**: ask Nebula to "search for X" while mentioning/messaging it, on either platform.
- **Discord Slash-Adjacent Command**: `!search query` (prefix command, not a slash command — see `discord_bot/search_command.py`).
- Costs 2 Nebula Coins either way.
- Provider is `google` or `tavily`, selected via `SEARCH_PROVIDER`. If the selected provider's credentials are missing, search is disabled entirely (no fallback to the other provider), and Nebula admins get a one-time DM about it on Discord startup.

## Database Structure

See README.md's Database Schema table for the full list. The short version: everything hangs off `nebula_user_id` (from `nebula_users`), and `platform_identities` is the only table that knows about specific platform user IDs. `DatabaseManager.list_admin_platform_identities(platform)` is a small, read-only helper on top of this same schema (a join of `nebula_users.is_admin = 1` against `platform_identities`), used for one-off admin notifications (currently: the AI-misconfiguration notice on Telegram — see "Provider Resolution" above) where a direct per-platform admin lookup is possible.

## Best Practices

### Security
1. Never commit API keys or `.env` to version control.
2. Treat `ADMIN_BOOTSTRAP_KEY` like a root password — long, random, used once, never shared.
3. On Telegram, `/signup` and `/login` necessarily put a password in the chat's own message history (Telegram bots can't delete a user's own message in a private chat) — Nebula shows a clear warning after each of these telling you to delete that message yourself. Discord avoids this via ephemeral slash command parameters, which don't have the same limitation.
4. Sync codes (`/sync` → `/verify`) expire after 10 minutes and are single-use, specifically so a leaked code has a short, bounded window of usefulness.

### Performance
1. Prefer the model-driven natural-language interface over direct commands where both exist — it's what most users will reach for anyway.
2. Monitor memory via `/memory_stats` before it becomes a blocking issue.
3. Check `/admin_logs` for an audit trail across both platforms.

---

For more information, see README.md or CHANGELOG.md.
