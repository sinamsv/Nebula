# Changelog

All notable changes to Nebula will be documented in this file.

## [1.5.0] - 2026-07-18

### Added
- **Web panel (`web_backend/`)**: a third platform adapter, alongside Discord and Telegram — a FastAPI backend (paired with a Next.js frontend) that lets users sign up, log in, chat with Nebula (including image uploads), link Discord/Telegram, and — for admins — review pending signups and manage coin balances, all through a browser. Structurally parallel to `discord_bot/`/`telegram_bot/`: a thin adapter over the same `core/` and `ai/` logic, using `platform="web"` in `platform_identities` exactly like `"discord"`/`"telegram"`.
  - Auth: JWT-based (`PyJWT`, HS256), issued on signup/login, validated on every authenticated request via `Authorization: Bearer <token>`. New `JWT_SECRET` env var.
  - **Multi-chat support (web-only)**: unlike Discord/Telegram (which keep their existing single continuous conversation per account, completely unchanged), the web panel supports multiple independently-named chats per account. New `chats` table; `conversation_history` gains a nullable `chat_id` column — `NULL` means the legacy Discord/Telegram single-thread history (existing rows and existing query paths are entirely unaffected), a real `chat_id` scopes a message to one web chat. **Each web chat has its own independent 200,000-token memory cap** — not pooled with the account's shared Discord/Telegram cap, and not pooled with the account's other web chats.
  - `core/memory.py`'s `MemoryManager` methods all gained an optional `chat_id` parameter (default `None`, preserving exact prior behavior) to support this without any changes needed on the Discord/Telegram side.
  - **Real multimodal image support (web-only, a capability upgrade)**: `POST /api/v1/chat/{id}/messages/image` forwards uploaded images to the AI provider as actual image content (not just a text placeholder). `ai/providers/base.py`'s `BaseProvider.call()` gained an optional `images` parameter (default `None`, a complete no-op for Discord/Telegram, which never pass it); each provider (OpenAI, Anthropic, Google) translates it into its own SDK's multimodal content-block shape, verified via live SDK inspection. Discord/Telegram continue to only send a `"[User attached N image(s)]"` text note, unchanged.
  - Per-message tool toggle: the web chat endpoint accepts `{"tools": {"search": false}}` to omit the search tool for that turn — `AIHandler.get_available_tools()` gained an `enable_search` parameter (default `True`, unchanged for Discord/Telegram).
  - Full API surface: `/api/v1/auth/{signup,login,google,google/callback,bootstrap-status}`, `/api/v1/chat` (list/create), `/api/v1/chat/{id}` (get/rename/delete), `/api/v1/chat/{id}/messages(/image)`, `/api/v1/users/me/coins` (self-only), `/api/v1/users/{id}/coins` (admin-only modify), `/api/v1/sync/{platform}`, `/api/v1/platforms`, `/api/v1/admin/users/pending`, `/api/v1/admin/users/{id}/review`, `/api/v1/admin/platforms`.
  - `core/auth.py`: new `AuthManager.approve_user_by_id()`, an id-based sibling to the existing username-based `approve_user()` (which Discord/Telegram's `/approve_user` command keeps using unchanged) — needed since the web admin review endpoint targets a `nebula_user_id` in its path rather than a username.
- **Google OAuth infrastructure (not wired to any tool yet)**: `GET /api/v1/auth/google` + `GET /api/v1/auth/google/callback` take a user through Google's consent flow and land their tokens in a new `oauth_connections` table, **encrypted** (via `cryptography`'s Fernet, new `core/crypto.py` module, new `OAUTH_TOKEN_ENCRYPTION_KEY` env var) rather than hashed — unlike `password_hash`, OAuth tokens must be recoverable in plaintext to eventually call Google's APIs. Entirely optional/skippable: no part of Nebula requires connecting Google. No actual Sheets/Calendar tool is built this release — this is groundwork only.
- **Web adapter startup**: `main.py` gained a third adapter branch, gated on `WEB_ENABLED=true` (plus `JWT_SECRET` and `OAUTH_TOKEN_ENCRYPTION_KEY`), served in-process via `uvicorn.Server` alongside Discord/Telegram under the same `asyncio.gather()` — still just `python main.py`, no separate backend process to run.
- **Docker**: `Dockerfile` now `EXPOSE`s port 8000 (harmless no-op when `WEB_ENABLED` is unset); `docker-compose.yml` publishes `${WEB_PORT:-8000}:8000`.

### Changed
- **`requirements.txt`**: added `fastapi`, `uvicorn[standard]`, `pyjwt`, `cryptography`, `python-multipart`, `httpx`.
- **`.env.sample`**: documents all new web-adapter env vars (`WEB_ENABLED`, `WEB_PORT`, `WEB_FRONTEND_URL`, `JWT_SECRET`, `OAUTH_TOKEN_ENCRYPTION_KEY`, `GOOGLE_OAUTH_CLIENT_ID`/`SECRET`/`REDIRECT_URI`).
- **`core/database.py`**: `add_message()`, `get_conversation_history()`, `get_total_tokens()`, `reset_conversation()` all gained an optional `chat_id` parameter (default `None`, preserving exact prior SQL/behavior for every existing Discord/Telegram call site). New `chats` and `oauth_connections` tables; existing databases auto-migrate on startup (`ALTER TABLE conversation_history ADD COLUMN chat_id` runs once, guarded by a `PRAGMA table_info` check — pre-existing rows get `chat_id = NULL` automatically, which is exactly the "legacy history" meaning needed, no backfill required).
- **`ai/handler.py`**: `handle_turn()` gained optional `chat_id`, `images`, and `enable_search` parameters, all defaulting to values that preserve exact prior behavior for Discord/Telegram (`None`, `None`, `True` respectively).

### Fixed
- N/A — this release is additive only, no bug fixes.

### Notes
- Verified via a full regression pass: the project's own pre-existing `test_handler_integration.py` (5 tests) and `test_providers.py` (8 tests) both pass unchanged against this release's `ai/handler.py` and `ai/providers/*.py`, confirming zero behavior change for Discord/Telegram. New `tests/test_web_backend_integration.py` (7 tests) covers the web adapter end-to-end, including a dedicated test confirming a Discord-originated message and a web chat message for the same account never appear in each other's history.

## [1.4.0] - 2026-07-14

### Added
- **Multi-provider AI support**: Nebula can now use Anthropic, Google (Gemini), OpenAI, xAI, OpenRouter, or Groq as its AI backend, selected via the new `AI_PROVIDER` + `AI_API_KEY` environment variables. Previously only OpenAI-compatible endpoints (via `OPENAI_API_KEY`/`OPENAI_BASE_URL`) were supported.
  - `ai/providers/`: a new provider abstraction layer. `ai/handler.py` no longer imports any AI SDK directly — it talks to a shared `BaseProvider` interface (`call()` / `append_tool_round()`), implemented once per SDK: `openai_sdk.py` (covers OpenAI, xAI, OpenRouter, and Groq — all four are OpenAI-compatible with no dedicated SDK of their own), `anthropic_sdk.py`, and `google_sdk.py` (using the current `google-genai` package).
  - `ai/config.json`: per-provider `base_url`, `temperature`, and `thinking_level` settings. `thinking_level` (`"low"`/`"medium"`/`"high"`/`null`) is a single word-based setting translated appropriately per provider — passed straight through as `reasoning_effort` for OpenAI-family providers, converted to a numeric `budget_tokens` for Anthropic, and passed as Gemini's own `ThinkingLevel` enum for Google.
- **Graceful AI misconfiguration handling**: if no AI provider is configured (or the configuration is incomplete/invalid), Nebula no longer fails to start — non-AI features (`/coin`, `/signup`, `/login`, moderation tools, etc.) keep working. Users attempting to chat with Nebula see a short, generic notice; admins additionally receive a detailed one-time notice on startup (console output on both platforms, a DM on Discord, a direct message on Telegram) naming the specific configuration problem.
  - `DatabaseManager.list_admin_platform_identities(platform)`: a new read-only helper for looking up every admin's linked identity on a given platform, used by the Telegram-side admin notification above.

### Changed
- **`requirements.txt`**: added `anthropic>=0.116.0` and `google-genai>=2.11.0`.
- **`.env.sample`**: documents the new `AI_PROVIDER`/`AI_API_KEY`/`AI_MODEL` variables. The previous `OPENAI_API_KEY`/`OPENAI_BASE_URL` pair still works if set (including `OPENAI_BASE_URL` overrides, e.g. for a Gemini-via-OpenAI-compatible-endpoint setup) but is now documented as deprecated, with a console warning printed when it's used.

### Fixed
- N/A — this release is additive/refactoring only, no bug fixes.

### Notes
- The pre-existing behavior where a Nebula Coin is spent for a turn even if it then fails because the AI backend isn't configured is **unchanged** by this release — this was true before the provider abstraction existed too, and wasn't in scope for this change (see MIGRATION_GUIDE.md).

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
