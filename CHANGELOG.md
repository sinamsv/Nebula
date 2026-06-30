# Changelog

All notable changes to Nebula Discord Bot will be documented in this file.

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
