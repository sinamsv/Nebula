# Nebula - AI-Powered Multi-Platform Assistant

![Python Version](https://img.shields.io/badge/python-3.9+-blue)
![Discord.py](https://img.shields.io/badge/discord.py-2.3+-blue)
![python-telegram-bot](https://img.shields.io/badge/python--telegram--bot-21+-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-web%20panel-teal)
[![Documentation](https://img.shields.io/badge/Docs-Documentation-blue)](./DOCUMENTATION.md)
[![Migration](https://img.shields.io/badge/Guide-Migration-orange)](./MIGRATION_GUIDE.md)
[![License](https://img.shields.io/badge/License-MIT-green)](./LICENSE.txt)

Nebula is an AI-powered assistant reachable from **Discord, Telegram, and a web panel**, sharing one account, one conversation memory, and one coin balance across whichever platform(s) you talk to it from. Ask it things, have it search the web, upload images for it to actually see (web), and — for admins on Discord — moderate your server, all through natural conversation.

## ✨ Features

### 🤖 AI-Powered Conversations
- Natural language processing, model configurable via `AI_MODEL` across six providers (OpenAI, Anthropic, Google, xAI, OpenRouter, Groq)
- Context-aware responses that remember previous conversations — **across platforms**, not just within one (Discord/Telegram) — or scoped to an individual chat (web's multi-chat mode)
- Addresses users by their display name for personal engagement
- Handles replies to messages intelligently, on Discord and Telegram
- **Real image understanding on web**: attach an image to a web chat message and Nebula actually sees it, not just a placeholder note

### 🌍 Multi-Platform, One Account
- **Discord**: mention the bot in a server channel, or just DM it directly — no mention needed in DMs.
- **Telegram**: message it directly in a private chat, or `@mention` it in a group.
- **Web**: sign up or log in at the web panel, then chat directly — no mention needed, ever.
- **One Nebula account, everywhere**: sign up once, then link additional platforms with `/sync` (Discord or web) instead of creating a separate account per platform.
- Admin status, memory, and coin balance are all properties of your **Nebula account**, not any single platform.

### 💬 Multiple Chats (Web Only)
- Unlike Discord/Telegram (one continuous conversation per account), the web panel lets you keep multiple independently-named chats going at once.
- Each web chat has its **own** 200,000-token memory capacity — separate from your shared Discord/Telegram history, and separate from your other web chats.
- Create, rename, and delete chats freely; nothing you do in one chat affects another.

### 🔗 Cross-Platform Account Linking (`/sync` + `/verify`)
Already have a Nebula account and want to use another platform too?
1. On Discord (`/sync platform:telegram username:<your Nebula username>`) or on the web panel's Platforms page — you'll get a one-time code.
2. On Telegram: message the bot `/start` if you haven't already, then send `/verify username:<your Nebula username> code:<the code>`.
3. Done — your memory and coin balance now carry over.

Codes expire after 10 minutes and can only be used once. Linking is deliberately one-directional: Discord and the web panel can each *issue* a code; only Telegram *consumes* one via `/verify` today.

### 👤 Accounts & Approval
- Sign up on Discord (`/signup`), Telegram (`/signup username:<n> password:<p>`), or the web panel (a signup form) — pending admin approval by default.
- Log in on any platform to link an existing account to a new platform identity directly.
- **Sign in with Google** (web only): finds-or-creates a Nebula account from your Google account's email — entirely optional, not required for anything else to work.
- The very first admin account is created via a one-time `ADMIN_BOOTSTRAP_KEY`, usable from Discord, Telegram, or the web signup form (whichever you use first); every admin after that is promoted with `/add_admin` (Discord) or approved/promoted from the web admin panel.

### 💾 Memory Management
- SQLite-backed conversation history, scoped to your Nebula account (Discord/Telegram) or to an individual web chat.
- 200,000 token capacity per scope; new messages are refused with a clear message once full, rather than being silently dropped or auto-wiped.
- `/memory_stats` and `/memory_reset` (Discord/Telegram) — available to any approved user, and apply to their own memory only. On web, deleting a chat (`DELETE /api/v1/chat/{id}`) is the equivalent "start fresh" action for that chat.

### 🌝 Nebula Coin System (Rate Limiting)
- **Starting Balance**: every account starts with **10 coins**, shared globally (not per-guild, per-chat, or per-platform).
- **Consumption**: 1 coin per AI message, 2 coins per web search.
- **Automatic Reset**: back to 10 (non-stacking) every 8 hours.
- `/coin` (Discord/Telegram) or `GET /api/v1/users/me/coins` (web) to check your balance; `/add_coin` (Discord/Telegram, admin-only) or `POST /api/v1/users/{id}/coins` (web, admin-only) to grant or set someone's balance.

### 🔍 Web Search Integration
- Google Custom Search or Tavily (an AI-native search API) — pick one via `SEARCH_PROVIDER`
- Available to all approved users, costs 2 Nebula Coins
- Web users can toggle search off for an individual message (`{"tools": {"search": false}}`); Discord/Telegram always offer it
- If the selected provider is misconfigured, search is disabled entirely (no silent fallback to the other provider) and admins are notified

### 🛡️ Admin Tools
- **Discord Only**: Kick, ban, and channel creation via natural-language AI request — inherently Discord Guild operations with no Telegram or web equivalent.
- **User Activity Check** (Discord): cross-platform account activity and memory usage for any linked user.
- **Admin Logs**: `/admin_logs` (Discord) — every admin action, across every platform, in one log.
- **Account Approval**: available from Discord (`/approve_user`, `/pending_users`, `/add_admin`) **and** from the web admin panel (`GET /api/v1/admin/users/pending`, `POST /api/v1/admin/users/{id}/review`) — admin status is Nebula-level, so promoting/approving someone from either surface applies everywhere they're linked.

### 🔐 Google OAuth (Infrastructure)
- Web users can connect a Google account. Tokens are stored **encrypted** (not hashed — they need to be recoverable), via `cryptography`'s Fernet.
- This is groundwork for future Google Sheets/Calendar tools — nothing uses these tokens yet, and connecting Google is entirely optional.

## 📋 Prerequisites

- Python 3.9 or higher
- A Discord Bot Token, a Telegram Bot Token, a configured web adapter, or any combination (at least one is required)
- An API key for at least one supported AI provider (OpenAI, Anthropic, Google, xAI, OpenRouter, or Groq)
- Google Custom Search or Tavily API key (optional, for search functionality)
- Google OAuth credentials (optional, only if you want to enable the web panel's "Connect Google" flow)

## 🚀 Installation

### 1. Clone or Download the Repository

```bash
git clone https://github.com/sinamsv/Nebula
cd Nebula
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

2. Edit `.env` and fill in your credentials. At minimum, you need `AI_PROVIDER`, `AI_API_KEY`, `AI_MODEL`, `ADMIN_BOOTSTRAP_KEY`. Note that the **web panel is mandatory** and always active, while Discord and Telegram remain optional:

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

#### Web Panel (Mandatory):
1. The web adapter is a core system feature and is always active.
2. Generate `JWT_SECRET`: `python3 -c "import secrets; print(secrets.token_urlsafe(64))"`
3. Generate `OAUTH_TOKEN_ENCRYPTION_KEY`: `python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`
4. (Optional) Fill in `GOOGLE_OAUTH_CLIENT_ID`/`SECRET`/`REDIRECT_URI` if you want to enable Google Sign-In/Connect — see [Google Cloud Console](https://console.cloud.google.com/apis/credentials).
5. The API serves on `BACKEND_PORT` (default `8000`). Pair it with the Next.js frontend, pointed at this API's base URL.

You don't need all three adapters — set whichever platform(s) you actually want to run. Nebula starts every adapter it's configured for and skips the rest.

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

Edit `system.txt` to customize Nebula's personality and behavior — shared across every platform, including web.

### 6. Run Nebula

```bash
python main.py
```

This starts the entire multi-platform ecosystem (Discord, Telegram, Web API, and the Next.js Web UI frontend) concurrently under a single, unified Python process.

On startup, `main.py` automatically orchestrates:
- Checking for missing or outdated Node.js dependencies in `web_frontend/` and running `npm install` automatically if needed.
- Checking for the production build (`.next/`) and running `npm run build` automatically if it is missing.
- Executing the frontend using `npm run start` (or `npm run dev` in local development if `NODE_ENV=development` is set).

All Next.js logs are forwarded and clearly prefixed directly to your Python console logs for easy debugging.

## 🎯 Usage

### Talking to Nebula

**Discord:**
```
@Nebula what's the weather like?
```
Or just DM the bot directly — no mention needed there.

**Telegram:**
```
[in a private chat with the bot] what's the weather like?
```
Or, in a group, `@mention` it the same way you would on Discord.

**Web:**
Log in at the web panel, open (or create) a chat, and just type — no mention needed, ever. Attach an image if you want Nebula to actually look at it.

*Note: each response costs 1 Nebula Coin, shared across whichever platform(s) you use.*

### Web API Quick Reference

```bash
# Sign up
curl -X POST http://localhost:8000/api/v1/auth/signup \
  -H "Content-Type: application/json" \
  -d '{"username": "sina", "password": "a-strong-password"}'

# Create a chat (using the access_token from signup/login)
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Authorization: Bearer <token>" -H "Content-Type: application/json" \
  -d '{"title": "General"}'

# Send a message
curl -X POST http://localhost:8000/api/v1/chat/<chat_id>/messages \
  -H "Authorization: Bearer <token>" -H "Content-Type: application/json" \
  -d '{"input": "hello Nebula!", "tools": {"search": true}}'
```

See DOCUMENTATION.md's "Web Panel" section for the full API surface.

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
| `/verify username:<n> code:<c>` | Anyone | Complete a `/sync` started on Discord or the web panel |
| `/coin` | Approved users | Show your Nebula Coin balance |
| `/memory_stats` / `/memory_reset` | Approved users | View or clear your own memory |
| `/add_coin username:<n> amount:<a> mode:<add\|set>` | Admin | Add to or set a user's coin balance |

#### Web (HTTP API, see DOCUMENTATION.md for the full list)
| Endpoint | Who | Description |
|---|---|---|
| `POST /api/v1/auth/signup`, `/login` | Anyone | Create/access a Nebula account from the browser |
| `GET /api/v1/auth/google`, `/google/callback` | Anyone | Sign in / connect with Google |
| `GET`/`POST /api/v1/chat` | Approved | List / create chats |
| `POST /api/v1/chat/{id}/messages(/image)` | Approved | Chat with Nebula, optionally with an image |
| `POST /api/v1/sync/{platform}` | Approved | Generate a code to link Discord or Telegram |
| `GET /api/v1/users/me/coins` | Approved | Your own coin balance |
| `GET /api/v1/admin/users/pending`, `POST /api/v1/admin/users/{id}/review` | Admin | Review pending signups |

Admin moderation commands (kick, ban, create channel) remain Discord-only today.

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
├── system.txt                 # AI system prompt (shared across every platform)
├── requirements.txt
├── .env.sample
├── core/                      # Platform-agnostic business logic
│   ├── database.py            #   SQLite layer: nebula_users, platform_identities, memory, coins, sync codes, admin log, chats, oauth_connections
│   ├── auth.py                #   Signup/login/approval + cross-platform account sync
│   ├── memory.py              #   Per-account (or per-web-chat) conversation memory, 200k token cap
│   ├── coins.py                #   Nebula Coin balance/spend/reset logic
│   └── crypto.py              #   Fernet encryption for OAuth tokens at rest
├── ai/
│   ├── handler.py             # Platform-agnostic conversation turn handling (model calls, tool dispatch, multimodal)
│   ├── config.json            # Per-provider base_url/temperature/thinking_level settings
│   └── providers/              # One file per AI SDK, normalized behind a shared interface (multimodal-capable)
│       ├── base.py             #   BaseProvider, NormalizedResponse, NormalizedToolCall, ImageAttachment
│       ├── openai_sdk.py       #   OpenAI + xAI + OpenRouter + Groq
│       ├── anthropic_sdk.py    #   Anthropic
│       └── google_sdk.py       #   Google Gemini
├── tools/                     # AI-callable tools
│   ├── search.py               #   Platform-agnostic (Google / Tavily)
│   └── moderation.py           #   Discord-only (kick/ban/create_channel need a discord.Guild)
├── discord_bot/                # Discord adapter
├── telegram_bot/                # Telegram adapter
└── web_backend/                 # Web adapter (FastAPI) -- thin, mirrors discord_bot/telegram_bot's structure
    ├── app.py                   #   FastAPI app factory
    ├── security.py               #   JWT issue/validate
    ├── dependencies.py            #   Shared-instance + identity dependency injection
    ├── schemas/                   #   Pydantic request/response models
    └── routes/                    #   auth.py, chat.py, coins.py, sync.py, admin.py
```

## 🗄️ Database Schema

Schema is organized around **Nebula accounts**, not guilds, channels, or web sessions — this is what makes cross-platform identity, memory, and coin balances work.

| Table | Purpose |
|---|---|
| `nebula_users` | A Nebula account: username, password hash, display name, admin/approval status |
| `platform_identities` | Links a platform-specific ID (Discord user ID, Telegram user ID, web session, Google email) to a `nebula_user_id`. One account can have many platform identities. |
| `platform_sync_codes` | One-time codes for the `/sync` (Discord or web) → `/verify` (Telegram) account-linking flow |
| `chats` | **(New in 1.5.0)** Web-only: one row per named chat, scoped to a `nebula_user_id` |
| `conversation_history` | Memory. `chat_id IS NULL` = legacy account-wide history (Discord/Telegram); `chat_id = <int>` = scoped to one web chat |
| `coin_balances` | Nebula Coin balance and reset timer, per `nebula_user_id`, global across platforms |
| `oauth_connections` | **(New in 1.5.0)** Encrypted OAuth tokens (Google), per `(nebula_user_id, provider)` |
| `admin_actions_log` | Every admin action, across every platform |
| `bootstrap_state` | Tracks whether the one-time `ADMIN_BOOTSTRAP_KEY` has been claimed |
| `server_settings` | Discord-specific, legacy per-guild settings |

## ⚙️ Configuration

### Memory Management
- **Max Tokens**: 200,000 per scope — one shared scope per Nebula account for Discord/Telegram, one independent scope per web chat.
- **Hard cap, not auto-reset**.
- **Token Counting**: `tiktoken`.

### AI Configuration
- **Provider**: set via `AI_PROVIDER` + `AI_API_KEY`. See `ai/config.json` for per-provider `base_url`/`temperature`/`thinking_level` settings.
- **Model**: set via `AI_MODEL`.
- **Max Tokens**: 2000 per response.
- **Multimodal images**: web-only, real forwarding to the model (not a text placeholder) — see DOCUMENTATION.md.
- **Legacy config**: `OPENAI_API_KEY` + `OPENAI_BASE_URL` still works if set, but is deprecated.

### Message Handling
- **Discord**: 2000-character limit, auto-split.
- **Telegram**: 4096-character limit, auto-split.
- **Web**: no artificial split — JSON response bodies, rendered by the frontend as-is.

### Web Panel
- `BACKEND_PORT`, `FRONTEND_PORT`, `WEB_FRONTEND_URL`, `JWT_SECRET`, `OAUTH_TOKEN_ENCRYPTION_KEY` — see `.env.sample`.
- Google OAuth (optional): `GOOGLE_OAUTH_CLIENT_ID`, `GOOGLE_OAUTH_CLIENT_SECRET`, `GOOGLE_OAUTH_REDIRECT_URI`.

## 🔒 Permissions Required

**Discord**: Read Messages/View Channels, Send Messages, Manage Messages, Embed Links, Read Message History, Kick Members, Ban Members, Manage Channels.

**Telegram**: no special bot permissions needed for private chats. For group use, disable Privacy Mode via BotFather's `/setprivacy` if you want it to see un-mentioned messages.

**Web**: none beyond normal HTTPS network access to wherever you deploy the API and frontend.

## 🤝 Contributing

Contributions are welcome! Please feel free to submit pull requests or open issues for bugs and feature requests.

## 📄 License

MIT License

---

**Enjoy using Nebula! 🌟**
