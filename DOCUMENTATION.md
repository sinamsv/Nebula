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
       │
       ├── discord_bot/  (adapter: translates discord.Message <-> handle_turn())
       └── telegram_bot/ (adapter: translates telegram.Update <-> handle_turn())
```

The reason this split exists: `ai/handler.py` has zero platform-specific imports (no `discord.py`, no `python-telegram-bot`). It takes plain strings in (`source_platform`, `platform_user_id`, `display_name`, `message_text`) and returns a plain `TurnResult` out. Each adapter's job is entirely translation — turning a platform-native message object into that plain call, and rendering the result back as platform-native messages. This is what let Telegram support get added without touching a single line of `ai/handler.py`, `core/auth.py`'s identity logic, or `core/memory.py`.

The one deliberate exception is guild moderation (kick/ban/create_channel): these are inherently Discord Guild API operations with no Telegram equivalent, so `handle_turn()` accepts an optional `discord_guild` parameter that Telegram's adapter simply never passes, which automatically excludes those tools from what the AI model is offered.

### Component Responsibilities

- **main.py**: constructs every shared instance once, starts every adapter with a configured token via `asyncio.gather()`.
- **core/database.py**: SQLite abstraction for every table (accounts, platform links, sync codes, memory, coins, admin log).
- **core/auth.py**: signup/login/approval, plus the `/sync` → `/verify` cross-platform linking flow.
- **core/memory.py**: per-account conversation memory and the 200k-token cap.
- **core/coins.py**: Nebula Coin balance, spend, and reset logic.
- **ai/handler.py**: one conversational turn end-to-end — identity/memory/coin gating, the model call, tool dispatch, memory writes.
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

### Message Processing Flow (both platforms)

1. **Trigger check** (adapter-specific): Discord requires a mention in guild channels, none in DMs; Telegram requires a mention in groups, none in private chats.
2. **`ai.handler.AIHandler.handle_turn()`** — identical on both platforms from here on:
   - Resolve approved identity (or return a specific blocked reason).
   - Check memory isn't full.
   - Spend 1 coin (or return an insufficient-funds message).
   - Load conversation context (cross-platform, per-account).
   - Call the model with the tools available to this identity/context.
   - Dispatch any tool calls.
   - Write both the user's message and the assistant's reply to memory.
3. **Adapter renders the result** back as platform-native messages, chunked to that platform's character limit (2000 for Discord, 4096 for Telegram).

### Tool System

Tools are defined in OpenAI's function-calling format. Which tools are offered depends on the caller's admin status AND whether the platform passed a `discord_guild` (only Discord ever does):

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

See README.md's Database Schema table for the full list. The short version: everything hangs off `nebula_user_id` (from `nebula_users`), and `platform_identities` is the only table that knows about specific platform user IDs.

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
