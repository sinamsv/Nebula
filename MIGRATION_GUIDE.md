# Nebula Bot - Migration Guide

## Upgrading to Version 1.3.0

Version 1.3.0 adds a Telegram adapter alongside Discord, changes how Discord DMs behave, and restructures `main.py` and the coin system to support running multiple adapters at once. Nothing about your *data* needs migrating (same `nebula_users`/`platform_identities`-based schema as 1.2.0, just one new table), but a few things about how you run and configure the bot do change.

### 1. `main.py` now launches differently

**What changed:** `main.py` used to only ever start Discord. It now constructs the shared core instances once and starts *every adapter you've configured a token for*, concurrently via `asyncio.gather()`.

**What you need to do:**
- Nothing, if you only use Discord — set `DISCORD_TOKEN` like before, leave `TELEGRAM_BOT_TOKEN` blank, and Nebula behaves the same as it always did (`python main.py` still starts just Discord).
- To add Telegram: get a token from [@BotFather](https://t.me/BotFather) and set `TELEGRAM_BOT_TOKEN` in `.env`. Both adapters will start on the same `python main.py` run.
- Update dependencies (`pip install -r requirements.txt`) — it now includes `python-telegram-bot`.

### 2. Discord DMs no longer require a mention

**What changed:** previously, Nebula only responded in a DM if you mentioned it (same rule as a server channel). Now, *any* message you send Nebula in a DM gets a response — no mention needed. Mentioning it still works fine in DMs too (the mention text is just stripped, same as before); it's simply no longer *required* there. Server channels are unaffected — mentioning the bot is still required there.

**What you need to do:** nothing — this is a behavior change, not a config change. If you were relying on Nebula *ignoring* un-mentioned DMs for some reason, that's no longer the case.

### 3. Coin balance logic moved to `core/coins.py`

**What changed:** the Nebula Coin balance/spend/reset logic used to live inside a Discord-specific cog (`discord_bot/coin_commands.py`, formerly holding a class also named `CoinManager`). It's now `core/coins.py`'s `CoinManager` class, shared between both adapters. The Discord cog is now `CoinCommands` (renamed to avoid confusion with the new shared class) and just wraps slash commands around it.

**What you need to do:** nothing if you're running the bot as-is. If you had any custom code reaching into `bot.get_cog('CoinManager')`, update it to use `bot.coin_manager` directly instead (a `core.coins.CoinManager` instance, set once in `discord_bot/client.py`'s `build_bot()`).

### 4. New: cross-platform account linking (`/sync` + `/verify`)

If you already have a Nebula account on Discord and want to use it from Telegram too (or vice versa), you don't need to `/signup` a second, separate account:
- On Discord: `/sync platform:telegram username:<your Nebula username>`
- On Telegram: `/verify username:<your Nebula username> code:<the code you got on Discord>`

See README.md's "Cross-Platform Account Linking" section for the full flow and why the direction is fixed (Discord issues the code, Telegram consumes it — not the reverse).

### 5. Database

A new table, `platform_sync_codes`, is created automatically on first run of 1.3.0, same as `coin_balances` was in 1.2.0 — no manual SQL required.

---

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

### Telegram commands aren't showing up
1. Telegram commands take effect immediately — no propagation delay like Discord's global sync. If they're still not appearing, confirm `TELEGRAM_BOT_TOKEN` is set correctly and check the console for a "Failed to set Telegram command descriptions" warning on startup.
2. In a group chat, make sure the bot can actually see messages — check Privacy Mode via [@BotFather](https://t.me/BotFather)'s `/setprivacy` if it isn't responding to @mentions there.

### Database errors
1. Ensure the bot has write permissions in its directory.
2. If you see "table already exists" errors, ensure you haven't manually modified the schema in a way that conflicts with the new tables.

### API Errors
1. Double-check your `.env` file against `.env.sample`.
2. Verify that your `AI_MODEL` is supported by your provider.
3. If using Gemini, ensure your `OPENAI_BASE_URL` is set correctly.
