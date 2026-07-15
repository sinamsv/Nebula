# Nebula - AI-Powered Multi-Platform Assistant

![Python Version](https://img.shields.io/badge/python-3.9+-blue)
![Discord.py](https://img.shields.io/badge/discord.py-2.3+-blue)
![python-telegram-bot](https://img.shields.io/badge/python--telegram--bot-21+-blue)
[![Documentation](https://img.shields.io/badge/Docs-Documentation-blue)](./DOCUMENTATION.md)
[![Migration](https://img.shields.io/badge/Guide-Migration-orange)](./MIGRATION_GUIDE.md)
[![License](https://img.shields.io/badge/License-MIT-green)](./LICENSE.txt)

Nebula is an AI-powered assistant reachable from **Discord and Telegram**, sharing one account, one conversation memory, and one coin balance across whichever platform(s) you talk to it from. Ask it things, have it search the web, and — for admins on Discord — moderate your server, all through natural conversation.

## ✨ Features

### 🤖 AI-Powered Conversations
- Natural language processing, model configurable via `AI_MODEL` (OpenAI-compatible: OpenAI, Gemini, and other providers)
- Context-aware responses that remember previous conversations — **across platforms**, not just within one
- Addresses users by their display name for personal engagement
- Handles replies to messages intelligently, on both Discord and Telegram

### 🌍 Multi-Platform, One Account
- **Discord**: mention the bot in a server channel, or just DM it directly — no mention needed in DMs.
- **Telegram**: message it directly in a private chat, or `@mention` it in a group.
- **One Nebula account, everywhere**: sign up once, then link additional platforms with `/sync` (see below) instead of creating a separate account per platform.
- Admin status, memory, and coin balance are all properties of your **Nebula account**, not any single platform.

### 🔗 Cross-Platform Account Linking (`/sync` + `/verify`)
Already have a Nebula account on Discord and want to use Telegram too (or vice versa)?
1. On Discord: `/sync platform:telegram username:<your Nebula username>` — you'll get a one-time code.
2. On Telegram: message the bot `/start` if you haven't already, then send `/verify username:<your Nebula username> code:<the code>`.
3. Done — your memory and coin balance now carry over to Telegram too.

Codes expire after 10 minutes and can only be used once. The direction is deliberately Discord → Telegram (not the reverse): Telegram won't let a bot message someone who hasn't messaged it first, so the code has to be carried over by you rather than delivered automatically.

### 👤 Accounts & Approval
- `/signup` to create a Nebula account (on either platform) — pending admin approval by default.
- `/login` to link an existing account to a new platform identity directly (an alternative to `/sync` if you'd rather just re-enter your password on the new platform).
- The very first admin account is created via a one-time `ADMIN_BOOTSTRAP_KEY` (see Installation below); every admin after that is promoted with `/add_admin` on Discord.

### 💾 Memory Management
- SQLite-backed conversation history, scoped to your Nebula account (not to a Discord channel or Telegram chat)
- 200,000 token capacity per account; new messages are refused with a clear message once full, rather than being silently dropped or auto-wiped
- `/memory_stats` and `/memory_reset` — available to any approved user, and apply to their own memory only

### 🌝 Nebula Coin System (Rate Limiting)
- **Starting Balance**: every account starts with **10 coins**, shared globally (not per-guild, per-chat, or per-platform).
- **Consumption**: 1 coin per AI message, 2 coins per web search.
- **Automatic Reset**: back to 10 (non-stacking) every 8 hours.
- `/coin` to check your balance; `/add_coin` (Discord, admin-only) to grant or set someone's balance.

### 🔍 Web Search Integration
- Google Custom Search or Tavily (an AI-native search API) — pick one via `SEARCH_PROVIDER`
- Available to all approved users, costs 2 Nebula Coins
- If the selected provider is misconfigured, search is disabled entirely (no silent fallback to the other provider) and admins are notified

### 🛡️ Admin Tools (Discord Only, Administrator-Only)
Kick, ban, and channel creation are inherently Discord Guild operations with no Telegram equivalent, so these stay Discord-only:
- **Kick / Ban User** via natural-language AI request
- **Create Channel** (text or voice, optionally inside a category) via AI request
- **User Activity Check**: cross-platform account activity and memory usage for any linked user
- **Admin Logs**: `/admin_logs` — every admin action, across both platforms, in one log
- **Account Approval**: `/approve_user`, `/pending_users`, `/add_admin` — admin status is Nebula-level, so promoting someone applies everywhere they're linked

## 📋 Prerequisites

- Python 3.9 or higher
- A Discord Bot Token, a Telegram Bot Token, or both (at least one is required)
- An API key for at least one supported AI provider (OpenAI, Anthropic, Google, xAI, OpenRouter, or Groq)
- Google Custom Search or Tavily API key (optional, for search functionality)

## 🚀 Installation

### 1. Clone or Download the Repository

```bash
git clone https://github.com/sinamsv/NebulaBot
cd NebulaBot
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure Environment Variables

1. Copy `.env.sample` to `.env`:
```bash
cp .env.sample .env
```

2. Edit `.env` and fill in your credentials. At minimum, you need `AI_PROVIDER`, `AI_API_KEY`, `AI_MODEL`, `ADMIN_BOOTSTRAP_KEY`, and **at least one** of `DISCORD_TOKEN` / `TELEGRAM_BOT_TOKEN`:

```env
DISCORD_TOKEN=your_discord_bot_token_here
TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here
AI_PROVIDER=google
AI_API_KEY=your_api_key_here
AI_MODEL=gemini-2.0-flash-001
ADMIN_BOOTSTRAP_KEY=  # generate per the instructions in .env.sample
```

### 4. Get Your API Keys

#### Discord Bot Token:
1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Create a new application → "Bot" section → "Reset Token" and copy it
3. Enable these Privileged Gateway Intents: Server Members Intent, Message Content Intent

#### Telegram Bot Token:
1. Open a chat with [@BotFather](https://t.me/BotFather) on Telegram
2. Send `/newbot` and follow the prompts (choose a name and a username ending in `bot`)
3. BotFather gives you a token that looks like `123456789:AAExampleTokenTextGoesHere` — copy it into `TELEGRAM_BOT_TOKEN`

You don't need both — set whichever platform(s) you actually want to run. Nebula starts every adapter it has a token for and skips the rest.

#### AI Provider Key:
Nebula supports six AI providers, selected via `AI_PROVIDER`. Set `AI_API_KEY` to that provider's key, and `AI_MODEL` to a model string that provider recognizes:

| `AI_PROVIDER` | Where to get a key | Example `AI_MODEL` |
|---|---|---|
| `openai` | [platform.openai.com](https://platform.openai.com/) | `gpt-5.2` |
| `anthropic` | [console.anthropic.com](https://console.anthropic.com/) | `claude-sonnet-4-6` |
| `google` | [Google AI Studio](https://aistudio.google.com/) | `gemini-3.1-pro-preview` |
| `xai` | [console.x.ai](https://console.x.ai/) | `grok-4.3` |
| `openrouter` | [openrouter.ai](https://openrouter.ai/) | `anthropic/claude-sonnet-4` |
| `groq` | [console.groq.com](https://console.groq.com/) | `llama-3.3-70b-versatile` |

`openai`, `anthropic`, and `google` talk to their official APIs directly. `xai`, `openrouter`, and `groq` are accessed as OpenAI-compatible endpoints — their base URLs are already configured for you in `ai/config.json`, no extra setup needed.

If you were using Nebula before this provider system existed, your old `OPENAI_API_KEY`/`OPENAI_BASE_URL` setup (e.g. pointed at Gemini) still works unchanged — see `.env.sample`'s deprecated section — but new setups should use `AI_PROVIDER` + `AI_API_KEY` instead.

#### Google Custom Search / Tavily (Optional):
- Google: [API Key](https://console.cloud.google.com/apis/credentials) + [Search Engine ID](https://programmablesearchengine.google.com/)
- Tavily: get a key at [app.tavily.com](https://app.tavily.com/)

### 5. Customize System Prompt (Optional)

Edit `system.txt` to customize Nebula's personality and behavior — shared across both platforms.

### 6. Run Nebula

```bash
python main.py
```

This starts every adapter you've configured a token for, concurrently. Check the console output to confirm which one(s) came up.

## 🎯 Usage

### Talking to Nebula

**Discord:**
```
@Nebula what's the weather like?
```
Or just DM the bot directly — no mention needed there:
```
[in a DM] what's the weather like?
```

**Telegram:**
```
[in a private chat with the bot] what's the weather like?
```
Or, in a group, `@mention` it the same way you would on Discord:
```
@YourBotUsername what's the weather like?
```

Both platforms understand replies: reply to a message and mention/message Nebula, and it'll see what you replied to as context.

*Note: each response costs 1 Nebula Coin, shared across whichever platform(s) you use.*

### Web Search

Ask Nebula to search for information on either platform:
```
@Nebula search for the latest AI news
```
Or on Discord, use the direct prefix command:
```
!search Python best practices
```
*Note: each search costs 2 Nebula Coins.*

### Commands

#### Discord (Slash Commands)
| Command | Who | Description |
|---|---|---|
| `/signup` | Anyone | Create a Nebula account, linked to this Discord identity |
| `/login` | Anyone | Link this Discord identity to an existing Nebula account |
| `/sync` | Approved users | Generate a code to link another platform to this account |
| `/coin` | Approved users | Show your Nebula Coin balance |
| `/memory_stats` / `/memory_reset` | Approved users | View or clear your own memory |
| `/add_coin` | Admin | Add to or set a user's coin balance |
| `/approve_user` / `/pending_users` / `/add_admin` | Admin | Account approval and admin management |
| `/admin_logs` | Admin | View recent admin action logs |

#### Telegram
| Command | Who | Description |
|---|---|---|
| `/start` | Anyone | Get started / see available commands |
| `/signup username:<n> password:<p>` | Anyone | Create a Nebula account, linked to this Telegram identity |
| `/login username:<n> password:<p>` | Anyone | Link this Telegram identity to an existing Nebula account |
| `/verify username:<n> code:<c>` | Anyone | Complete a `/sync` started on Discord |
| `/coin` | Approved users | Show your Nebula Coin balance |
| `/memory_stats` / `/memory_reset` | Approved users | View or clear your own memory |
| `/add_coin username:<n> amount:<a> mode:<add\|set>` | Admin | Add to or set a user's coin balance |

Admin moderation and account-approval commands (kick, ban, create channel, `/approve_user`, `/add_admin`, `/admin_logs`) are Discord-only today.

### AI-Powered Admin Tools (Discord, Administrators Only)

```
@Nebula kick @username for spamming
@Nebula ban @username for violating rules
@Nebula create a text channel called "general-chat" in the "Community" category
@Nebula check activity for @username
```

## 🏗️ Project Structure

```
nebula/
├── main.py                    # Launcher: builds shared core instances, runs every configured adapter
├── system.txt                 # AI system prompt (shared across platforms)
├── requirements.txt
├── .env.sample
├── core/                      # Platform-agnostic business logic
│   ├── database.py            #   SQLite layer: nebula_users, platform_identities, memory, coins, sync codes, admin log
│   ├── auth.py                #   Signup/login/approval + cross-platform account sync
│   ├── memory.py              #   Per-account conversation memory (200k token cap)
│   └── coins.py               #   Nebula Coin balance/spend/reset logic
├── ai/
│   ├── handler.py             # Platform-agnostic conversation turn handling (model calls, tool dispatch)
│   ├── config.json            # Per-provider base_url/temperature/thinking_level settings
│   └── providers/              # One file per AI SDK, normalized behind a shared interface
│       ├── base.py             #   BaseProvider, NormalizedResponse, NormalizedToolCall
│       ├── openai_sdk.py       #   OpenAI + xAI + OpenRouter + Groq (all plain AsyncOpenAI, different base_url)
│       ├── anthropic_sdk.py    #   Anthropic
│       └── google_sdk.py       #   Google Gemini
├── tools/                     # AI-callable tools
│   ├── search.py               #   Platform-agnostic (Google / Tavily)
│   └── moderation.py           #   Discord-only (kick/ban/create_channel need a discord.Guild)
├── discord_bot/                # Discord adapter (thin — wraps core/ai/tools for Discord)
│   ├── client.py
│   ├── auth_commands.py, sync_commands.py, coin_commands.py, memory_commands.py, admin_commands.py
│   ├── search_command.py
│   └── message_listener.py
└── telegram_bot/                # Telegram adapter (thin — wraps the exact same core/ai/tools)
    ├── client.py
    ├── auth_handlers.py, coin_handlers.py, memory_handlers.py
    ├── message_handler.py
    └── utils.py
```

## 🗄️ Database Schema

Schema is organized around **Nebula accounts**, not guilds or channels — this is what makes cross-platform identity, memory, and coin balances work.

| Table | Purpose |
|---|---|
| `nebula_users` | A Nebula account: username, password hash, display name, admin/approval status |
| `platform_identities` | Links a platform-specific ID (Discord user ID, Telegram user ID) to a `nebula_user_id`. One account can have many platform identities. |
| `platform_sync_codes` | One-time codes for the `/sync` → `/verify` account-linking flow |
| `conversation_history` | Memory, scoped to `nebula_user_id` (tagged with which platform each message originated on, but not scoped by it) |
| `coin_balances` | Nebula Coin balance and reset timer, per `nebula_user_id`, global across platforms |
| `admin_actions_log` | Every admin action, across both platforms |
| `bootstrap_state` | Tracks whether the one-time `ADMIN_BOOTSTRAP_KEY` has been claimed |
| `server_settings` | Discord-specific, legacy per-guild settings |

## ⚙️ Configuration

### Memory Management
- **Max Tokens**: 200,000 tokens per Nebula account
- **Hard cap, not auto-reset**: once full, new AI turns are refused with a message pointing to `/memory_reset`, rather than silently wiping history
- **Token Counting**: `tiktoken`

### AI Configuration
- **Provider**: set via `AI_PROVIDER` (`openai`, `anthropic`, `google`, `xai`, `openrouter`, or `groq`) + `AI_API_KEY`. See `ai/config.json` for per-provider `base_url`/`temperature`/`thinking_level` settings.
- **Model**: set via `AI_MODEL` (a model string your chosen provider recognizes)
- **Temperature**: 0.7 by default (configurable per-provider in `ai/config.json`)
- **Max Tokens**: 2000 per response
- **Extended thinking / reasoning**: optional, per-provider, via `ai/config.json`'s `thinking_level` field (`"low"`, `"medium"`, `"high"`, or `null` to disable)
- **Legacy config**: the older `OPENAI_API_KEY` + `OPENAI_BASE_URL` pair (including custom base URLs, e.g. for Gemini via its OpenAI-compatible endpoint) still works if set, but is deprecated in favor of `AI_PROVIDER` + `AI_API_KEY`

### Message Handling
- **Discord**: 2000-character limit, auto-split into multiple messages when exceeded
- **Telegram**: 4096-character limit, same auto-split behavior
- **Reply Context**: both platforms include the replied-to message in context when available

## 🔒 Permissions Required

**Discord**, the bot needs: Read Messages/View Channels, Send Messages, Manage Messages, Embed Links, Read Message History, Kick Members, Ban Members, Manage Channels.

**Telegram**, no special bot permissions are needed for private chats. For group use, the bot should be able to read messages in the group (disable Privacy Mode via BotFather's `/setprivacy` if you want it to see messages it isn't directly replying to or mentioned in).

## 🤝 Contributing

Contributions are welcome! Please feel free to submit pull requests or open issues for bugs and feature requests.

## 📄 License

MIT License

---

**Enjoy using Nebula! 🌟**
