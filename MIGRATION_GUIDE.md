# Nebula Bot - Migration Guide

## Upgrading to Version 1.2.0

Version 1.2.0 is a major update that transitions the bot to **Slash Commands** and introduces the **Nebula Coin System**.

### 1. Slash Command Migration

The bot has moved away from prefix-based commands (`!`) to modern Discord Slash Commands (`/`).

**What you need to do:**
- After updating the bot, you may need to wait up to an hour for global slash commands to appear in your server.
- For development, set `DEV_GUILD_ID` in your `.env` file to sync commands instantly to your test server.
- Remove any documentation or user guides that reference `!` commands.

**New Command Equivalents:**
- `!memory_stats` → `/memory_stats`
- `!reset_memory` → `/reset_memory`
- `!admin_logs` → `/admin_logs`
- (New) `/coin` - To check your coin balance.
- (New) `/add_coin` - For admins to manage user balances.
- (New) `/search` - For direct web searches.

### 2. Nebula Coin System

A new rate-limiting system is now in place to manage resource usage.

**Key Details:**
- Users start with 10 coins.
- Each AI response costs 1 coin.
- Each web search costs 2 coins.
- Balances reset every 8 hours.

**Admin Actions:**
- Admins can use `/add_coin` to give users more coins or set their balance to a specific amount if they need more frequent access.

### 3. Database Updates

The bot will automatically create the new `coin_balances` table upon the first run of version 1.2.0. No manual SQL execution is required.

---

## Upgrading to Version 1.1.0

### OpenAI Library Migration (v1.12.0+)

Version 1.1.0 updated the bot to use the latest OpenAI Python library structure.

**Requirements:**
- Update your dependencies: `pip install -r requirements.txt`
- Ensure your `openai` package is version `1.12.0` or higher.

**Key Changes:**
- The bot now uses the `AsyncOpenAI` client.
- Improved support for custom base URLs (e.g., Gemini via OpenAI API, Liara.ir).

---

## Troubleshooting Migration Issues

### Slash commands aren't showing up
1. Invite the bot again with the `applications.commands` scope enabled.
2. Ensure the bot has permissions to create slash commands in the server.
3. Wait up to 1 hour for global propagation, or use `DEV_GUILD_ID` for instant sync.

### Database errors
1. Ensure the bot has write permissions in its directory.
2. If you see "table already exists" errors, ensure you haven't manually modified the schema in a way that conflicts with the new tables.

### API Errors
1. Double-check your `.env` file against `.env.sample`.
2. Verify that your `AI_MODEL` is supported by your provider.
3. If using Gemini, ensure your `OPENAI_BASE_URL` is set correctly.
