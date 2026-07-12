# Changelog

All notable changes to Nebula will be documented in this file.

## [1.3.0] - 2026-07-12

### Added
- **Telegram Adapter**: Nebula is now reachable from Telegram, not just Discord, using the same Nebula account, memory, and coin balance on both platforms.
  - New Telegram commands: `/start`, `/signup`, `/login`, `/verify`, `/coin`, `/add_coin`, `/memory_stats`, `/memory_reset`.
  - Private (1:1) Telegram chats respond to any message, no mention required. Group chats require an `@mention` of the bot, mirroring Discord's server-channel behavior.
  - Admin moderation tools (kick, ban, create channel) remain Discord-only — Telegram has no equivalent concept of a guild to moderate.
- **`/sync` (Discord) → `/verify` (Telegram)**: A one-time, single-use code flow for linking a second platform to an existing Nebula account. Run `/sync platform:telegram username:<your username>` on Discord to get a code, then `/verify username:<your username> code:<code>` on Telegram to complete the link. Codes expire after 10 minutes and only the most recently issued code is ever valid.
- **Discord DMs now work without a mention**: previously Nebula only responded in DMs if you mentioned it, same as in a server. Since a DM is inherently a small, unambiguous conversation, any message you send Nebula in a DM now gets a response directly.
- **`core/coins.py`**: the Nebula Coin balance/spend/reset logic, previously living only inside a Discord-specific cog, is now a shared, platform-agnostic module — required so Telegram's `/coin` and `/add_coin` commands (and `ai/handler.py`'s per-message spending) all draw from the exact same logic instead of duplicating it.

### Changed
- **`main.py`** now constructs the shared database/auth/memory/coins/AI-handler instances once and runs every configured adapter concurrently via `asyncio.gather()`, instead of only ever starting Discord. Each adapter is independently optional — set `DISCORD_TOKEN`, `TELEGRAM_BOT_TOKEN`, or both in `.env` to control which one(s) start.
- **`discord_bot/client.py`** no longer constructs its own database/auth/memory/search instances; it now receives them from `main.py`, matching the sharing model above.
- **`discord_bot/coin_commands.py`** is now a thin wrapper around `core/coins.py` (renamed internally from `CoinManager` to `CoinCommands` to avoid confusion with the new shared class of the same former name).

### Fixed
- N/A — this release is additive/refactoring only.

## [1.2.0] - 2026-02-19

### Added
- **Nebula Coin System**: A new rate-limiting system for AI responses and searches.
  - Every user starts with 10 coins per guild.
  - 1 coin per AI message, 2 coins per search.
  - Automatic 8-hour reset (non-stacking).
- **Full Slash Command Migration**: All bot commands have been migrated to Discord Slash Commands.
  - New user commands: `/coin`, `/search`.
  - New admin commands: `/add_coin`, `/admin_logs`, `/memory_stats`, `/reset_memory`.
- **Database Schema Updates**: Added `coin_balances` table to track user budget and reset timers.
- **Improved Memory Management**: Enhanced memory tracking and reset capabilities via slash commands.
- **AI Model Upgrade**: Recommended model updated to `gemini-3.1-flash-lite` for superior performance and cost-efficiency.

### Changed
- Migrated all manual prefix commands (`!`) to slash commands (`/`).
- Updated `ai_handler.py` and `search_tool.py` to integrate with the Coin System.
- Refactored `bot.py` to handle slash command syncing and registration.
- Enhanced `DOCUMENTATION.md` and `README.md` to reflect the new command structure and features.

## [1.1.0] - 2026-02-19

### Changed
- **BREAKING**: Updated OpenAI library to version 1.12.0+ (from 0.28.x)
- Migrated from `openai.ChatCompletion.acreate()` to new `AsyncOpenAI` client structure
- Updated `ai_handler.py` to use `AsyncOpenAI` client with proper async handling
- Improved response handling for new OpenAI API structure
- All code and comments are now in English

## [1.0.0] - 2026-02-19

### Added
- Initial release of Nebula Discord Bot
- AI-powered conversations with GPT-4
- 400k token memory management
- Admin tools (kick, ban, create channels, user activity)
- Google Custom Search integration
- SQLite database with 4 tables
- Comprehensive documentation
