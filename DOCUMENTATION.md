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
8. [Web Panel](#web-panel)
9. [Google OAuth (Infrastructure)](#google-oauth-infrastructure)
10. [Database Structure](#database-structure)
11. [Best Practices](#best-practices)

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
       ├── telegram_bot/ (adapter: translates telegram.Update <-> handle_turn())
       └── web_backend/  (adapter: translates HTTP requests <-> handle_turn())
```

The reason this split exists: `ai/handler.py` has zero platform-specific imports (no `discord.py`, no `python-telegram-bot`, no `fastapi`). It takes plain strings in (`source_platform`, `platform_user_id`, `display_name`, `message_text`) plus a few optional extras (`chat_id`, `images`, `enable_search` — see below) and returns a plain `TurnResult` out. Each adapter's job is entirely translation — turning a platform-native message into that plain call, and rendering the result back as platform-native output. This is what let Telegram support, and later the web panel, get added without touching `core/auth.py`'s identity logic or breaking any existing adapter.

The same principle now applies one level deeper: `ai/handler.py` itself has zero AI-SDK-specific imports (no `openai`, `anthropic`, or `google.genai` types anywhere in that file). It talks only to an `ai.providers.base.BaseProvider` instance through two methods, `call()` and `append_tool_round()` — see "AI Provider Abstraction" below.

The one deliberate exception (at the platform-adapter layer) is guild moderation (kick/ban/create_channel): these are inherently Discord Guild API operations with no Telegram or web equivalent, so `handle_turn()` accepts an optional `discord_guild` parameter that Telegram's and web's adapters simply never pass, which automatically excludes those tools from what the AI model is offered.

### Component Responsibilities

- **main.py**: constructs every shared instance once, starts every adapter with a configured token/flag via `asyncio.gather()` — including the web adapter, served in-process via `uvicorn.Server` rather than a separate process.
- **core/database.py**: SQLite abstraction for every table (accounts, platform links, sync codes, memory, coins, admin log, web chats, OAuth connections).
- **core/auth.py**: signup/login/approval (both username-based, for Discord/Telegram/web forms, and id-based via `approve_user_by_id()`, for the web admin review endpoint), plus the `/sync` → `/verify` cross-platform linking flow.
- **core/memory.py**: per-account conversation memory and the 200k-token cap — either account-wide (Discord/Telegram) or per-web-chat, depending on whether a `chat_id` is passed.
- **core/coins.py**: Nebula Coin balance, spend, and reset logic.
- **core/crypto.py**: Fernet-based encryption/decryption for OAuth tokens at rest (`oauth_connections` table) — reversible, unlike `password_hash`'s one-way bcrypt.
- **ai/handler.py**: one conversational turn end-to-end — identity/memory/coin gating, AI provider resolution, the model call (optionally multimodal), tool dispatch, memory writes (optionally chat-scoped).
- **ai/providers/**: one file per AI SDK (`openai_sdk.py` covers OpenAI + xAI + OpenRouter + Groq, `anthropic_sdk.py`, `google_sdk.py`), each normalizing its SDK's request/response shape (including multimodal image content) behind `base.py`'s `BaseProvider` interface.
- **tools/search.py**: web search (Google or Tavily), platform-agnostic.
- **tools/moderation.py**: kick/ban/create_channel/user-activity-check — Discord-only, takes plain `discord.py` objects.
- **discord_bot/**, **telegram_bot/**: thin adapters, one file per concern (auth, coins, memory, the AI message handler), mirroring each other's structure.
- **web_backend/**: the third thin adapter — a FastAPI app (`app.py`), JWT auth (`security.py`), dependency injection (`dependencies.py`), and one route module per concern (`routes/auth.py`, `routes/chat.py`, `routes/coins.py`, `routes/sync.py`, `routes/admin.py`), mirroring the same "thin adapter, fat core" shape as the other two.

## Identity & Multi-Platform Accounts

A **Nebula account** (`nebula_users` table) is the actual unit everything hangs off of — memory, coin balance, and admin status all belong to a `nebula_user_id`, never to a Discord guild, a Telegram chat, or a web session. A platform identity (a specific Discord user ID, Telegram user ID, or web session) is linked to a Nebula account via `platform_identities`; one account can have several platform identities linked to it (that's the whole point).

Ways to end up with a platform identity linked to an account:
- **`/signup`** on Discord/Telegram, or `POST /api/v1/auth/signup` on web, creates a brand-new account and links the calling platform identity to it immediately.
- **`/login`** (Discord/Telegram) or `POST /api/v1/auth/login` (web) links the calling platform identity to an *existing* account, after verifying the username/password.
- **`/sync` (Discord or Web) + `/verify` (Telegram)** links a *new* platform identity to an *existing* account without re-entering a password on the new platform — instead, a one-time code generated on the issuing platform is carried over and consumed on Telegram. Web joined Discord as a second issuing platform in 1.5.0 (`POST /api/v1/sync/{platform}`) — it is deliberately **one-directional only**: web can generate a code to link Telegram (or Discord) to a web-created account, but there is no web-side `/verify`-equivalent endpoint to *consume* a code generated elsewhere, since web already has its own signup/login/Google-OAuth paths for account creation. See `core/auth.py`'s `generate_sync_code`/`verify_sync_code` for the full mechanics.
- **Google Sign-In** (`GET /api/v1/auth/google` → `GET /api/v1/auth/google/callback`): finds-or-creates a Nebula account keyed on the Google account's verified email (tracked as its own `platform="google"` identity, distinct from `platform="web"`), and issues a normal app JWT. See "Google OAuth" below.

For web specifically: a web session's `platform_user_id` is, by convention, `str(nebula_user_id)` itself — there's no separate native "web account id" the way Discord/Telegram each have their own user ID scheme (see `web_backend/dependencies.py`'s module docstring).

Unapproved accounts are not treated as if they don't exist — every gated action gives a specific "pending approval" message, not a generic failure, so a legitimate user always understands what to do next. On web, `require_approved_identity_web()` enforces this per-route (`web_backend/dependencies.py`), separate from plain JWT validation (`get_current_identity()`) — so e.g. checking your own pending status still works while you're unapproved.

## AI System

### AI Provider Abstraction

`ai/handler.py` doesn't call any AI SDK directly. Instead, on construction it resolves which provider to use (from `AI_PROVIDER`/`AI_API_KEY`, or the deprecated `OPENAI_API_KEY`/`OPENAI_BASE_URL` pair — see "Provider Resolution" below) and constructs exactly one `ai.providers.base.BaseProvider` implementation:

```python
class BaseProvider(ABC):
    async def call(self, messages, tools, system_prompt, images=None) -> NormalizedResponse: ...
    def append_tool_round(self, messages, response, tool_results) -> list: ...
```

- **`call()`** sends one request to the provider's API and returns a `NormalizedResponse` — a `content` string (or `None`, if the model only requested tools) plus a list of `NormalizedToolCall` objects (`id`, `name`, `arguments` — already parsed into a dict regardless of provider). The optional `images` parameter (a list of `ImageAttachment(data: bytes, mime_type: str)`) attaches images to the current turn — `None`/empty (the default, and the only value Discord/Telegram ever pass) is a complete no-op.
- **`append_tool_round()`** takes the messages sent, the response received, and the plain-string result of executing each tool call, and returns the new message list to send on the next round.

Three provider files implement this:
- **`ai/providers/openai_sdk.py`**: covers `openai`, `xai`, `openrouter`, and `groq`. Multimodal images become `{"type": "image_url", "image_url": {"url": "data:<mime>;base64,<data>"}}` content parts, verified against the installed SDK's `ChatCompletionContentPartImageParam`/`ImageURL` types.
- **`ai/providers/anthropic_sdk.py`**: the official `anthropic` SDK. Handles the `thinking_level` → `budget_tokens` translation. Multimodal images become `{"type": "image", "source": {"type": "base64", "media_type": <mime>, "data": <b64>}}` blocks, verified against `ImageBlockParam`/`Base64ImageSourceParam`.
- **`ai/providers/google_sdk.py`**: the official `google-genai` SDK. Multimodal images use `genai.types.Part.from_bytes(data=<bytes>, mime_type=<mime>)`, verified against the installed SDK's constructor signature.

In every provider, an image is only ever attached to the LAST message in the list (the current user turn) — never to history or to synthesized tool-round messages. `ai/handler.py`'s tool-calling loop only passes `images` on round one of a turn; every subsequent round passes `images=None`.

### Provider Configuration (`ai/config.json`)

Unchanged from 1.4.0 — see that section of this file's git history / MIGRATION_GUIDE.md if needed. No provider-config changes shipped in 1.5.0.

### Provider Resolution

Unchanged from 1.4.0.

### Message Processing Flow (all three platforms)

1. **Trigger check** (adapter-specific): Discord requires a mention in guild channels, none in DMs; Telegram requires a mention in groups, none in private chats; web has no trigger check at all — every `POST /api/v1/chat/{id}/messages(/image)` call is an explicit send action initiated by the frontend.
2. **`ai.handler.AIHandler.handle_turn()`** — identical on all three platforms from here on:
   - Resolve approved identity (or return a specific blocked reason).
   - Check memory isn't full — account-wide for Discord/Telegram (`chat_id=None`), or scoped to the specific web chat (`chat_id=<int>`) for web.
   - Spend 1 coin (or return an insufficient-funds message).
   - Check the AI provider is configured (or return the generic unconfigured message).
   - Load conversation context — account-wide or chat-scoped, matching the memory check above.
   - Call the model, through the resolved provider, with the tools available to this identity/context (web can additionally omit the search tool per-message via `enable_search=False`) and any attached images (web-only).
   - Dispatch any tool calls.
   - Write both the user's message and the assistant's reply to memory, in the same scope (account-wide or chat-scoped) as everything above.
3. **Adapter renders the result** back as platform-native output: chunked text messages (Discord/Telegram) or a JSON response body (web).

### Tool System

Unchanged in shape from 1.4.0 (still OpenAI function-calling format). `search` is offered to every approved user by default; web can omit it per-message via `{"tools": {"search": false}}` in the request body (`AIHandler.get_available_tools(..., enable_search=False)`) — Discord/Telegram have no equivalent per-message toggle, search is simply always offered there. `kick_user`, `ban_user`, `create_channel`, `user_activity_check` are only offered when `is_admin` AND `discord_guild is not None` — i.e., never on Telegram or web.

### Context Window Management

- History retrieval: last 50 messages by default for model context (per account for Discord/Telegram, per chat for web), 200 for web's own scrollback UI (`GET /api/v1/chat/{id}`).
- Token counting: `tiktoken`.
- Hard cap at 200,000 tokens — account-wide for Discord/Telegram, **independently per web chat** (see "Memory Management" below).

## Memory Management

### Token Tracking

```python
def count_tokens(self, text: str) -> int:
    return len(self.encoding.encode(text))
```

### Chat Scoping (web-only addition)

Every `MemoryManager` method (`get_usage`, `is_full`, `add_message_to_memory`, `get_conversation_context`, `reset_memory`) accepts an optional `chat_id` parameter, default `None`:
- `chat_id=None` (Discord/Telegram, always): exactly the pre-1.5.0 behavior — one continuous history, one shared 200k-token cap, per Nebula account, spanning both platforms.
- `chat_id=<int>` (web only): scoped entirely to that one chat. **Each web chat has its own independent 200k-token cap** — never pooled with the account's Discord/Telegram cap, and never pooled with the account's other web chats. A user with five web chats has 5 × 200k of memory capacity on top of their one shared Discord/Telegram cap.

This is implemented via a nullable `chat_id` column on `conversation_history` (see "Database Structure" below): `chat_id IS NULL` rows are the legacy account-wide history; `chat_id = <int>` rows belong to exactly one web chat.

### Memory Lifecycle

1. Message arrives → tokens counted.
2. If the relevant scope (account, for Discord/Telegram; that specific chat, for web) is already at/over the cap → the turn is refused *before* calling the model. Discord/Telegram point to `/memory_reset`; web returns a chat-specific message pointing to starting a new chat or clearing that one (`MemoryManager.full_chat_memory_message()`).
3. Otherwise the turn proceeds normally, and both the user's message and the assistant's reply are stored in that same scope.
4. At 90%+ capacity (but not yet full), a soft warning is appended to an otherwise-normal response — this warning's wording currently references `/memory_reset` regardless of platform; web clients should treat it as informational text rather than a literal slash command.

This is a **hard cap, not an auto-reset** — unchanged principle from before 1.5.0, now also applied per-chat on web.

### Memory Commands / Endpoints

- Discord/Telegram: `/memory_stats`, `/memory_reset` (account-wide, unchanged).
- Web: no dedicated memory-stats/reset endpoints shipped in 1.5.0 — `DELETE /api/v1/chat/{id}` removes a chat (and its history) entirely, which is the web-native equivalent of "starting fresh" for that one chat.

## Nebula Coin System

Unchanged from 1.4.0 in mechanics (10 starting coins, 1/message, 2/search, 8-hour non-stacking reset, shared globally per account across every platform including web). Web-specific access:
- `GET /api/v1/users/me/coins`: self-only — returns the caller's own balance. There is deliberately no `GET /api/v1/users/{id}/coins` for viewing someone else's balance (confirmed scope for this release; the closest existing admin capability is Discord's broader `user_activity_check` tool, which reports memory usage but not coin balance).
- `POST /api/v1/users/{id}/coins`: admin-only, add-to or set a target user's balance by `nebula_user_id` — the web-native equivalent of Discord/Telegram's `/add_coin`, same body shape (`{"amount": int, "mode": "add"|"set"}`).

## Admin Tools

Admin status is a property of the Nebula account (`is_admin` on `nebula_users`), not any platform's own role/permission system — including web, where `require_admin_identity_web()` gates every `/api/v1/admin/*` route.

### User Moderation (AI-Powered, Discord Only)

Unchanged from 1.4.0 — still Discord-only, no web or Telegram equivalent (see `tools/moderation.py`'s docstring for why).

### Account Approval

- Discord: `/pending_users`, `/approve_user username:<n> approve:<true|false>`, `/add_admin username:<n>` (unchanged, username-based).
- **Web** (new in 1.5.0): `GET /api/v1/admin/users/pending` (list), `POST /api/v1/admin/users/{id}/review` with body `{"status": "approved" | "rejected"}` — one combined endpoint rather than separate approve/reject endpoints, targeting a `nebula_user_id` in the path rather than a username. Backed by `AuthManager.approve_user_by_id()`, a new id-based sibling to the existing username-based `approve_user()` that Discord's commands keep using unchanged.

Reviewing signups from any platform works from any admin-capable surface (Discord or web) — approval is a property of the account, not scoped to where the review happened.

### Admin Logging

Unchanged — every admin action (from any platform, including web) is logged to `admin_actions_log`, viewable with `/admin_logs` on Discord.

## Search Functionality

Unchanged from 1.4.0 in mechanics. Web sends `{"input": "...", "tools": {"search": true|false}}` in its message body — `false` omits the search tool for that one turn (`AIHandler.get_available_tools(..., enable_search=False)`); Discord/Telegram have no equivalent per-message toggle.

## Web Panel

The web adapter (`web_backend/`) is a FastAPI application, structurally parallel to `discord_bot/`/`telegram_bot/`. It's meant to be paired with a Next.js frontend (not covered by this backend-focused documentation section) but is a complete, independently-testable HTTP API on its own.

### Auth

- JWT (`PyJWT`, HS256), signed with `JWT_SECRET`. `sub` claim is the `nebula_user_id` as a string — no other identity fact is embedded in the token, so an admin demotion or approval-status change takes effect on the very next request rather than waiting for token expiry.
- Tokens are long-lived (7 days) with no refresh/rotation flow in this release — a user simply logs in again after expiry.
- Every authenticated route expects `Authorization: Bearer <token>`.

### API Surface

Base path: `/api/v1`.

| Route | Method | Auth | Purpose |
|---|---|---|---|
| `/auth/bootstrap-status` | GET | none | Whether the one-time admin bootstrap key is still claimable (backs the signup form's "I'm admin" checkbox visibility) |
| `/auth/signup` | POST | none | Create account, get JWT |
| `/auth/login` | POST | none | Verify credentials, get JWT |
| `/auth/google` | GET | none | Redirect to Google's OAuth consent screen |
| `/auth/google/callback` | GET | none | Handle Google's redirect, issue JWT |
| `/chat` | GET | approved | List the caller's own chats |
| `/chat` | POST | approved | Create a new chat |
| `/chat/{id}` | GET | approved, owner | Get one chat's message history |
| `/chat/{id}` | PATCH | approved, owner | Rename a chat |
| `/chat/{id}` | DELETE | approved, owner | Delete a chat and its history |
| `/chat/{id}/messages` | POST | approved, owner | Send a text message, get Nebula's reply |
| `/chat/{id}/messages/image` | POST | approved, owner | Send a message with an attached image (multipart/form-data) |
| `/users/me/coins` | GET | approved | Caller's own coin balance |
| `/users/{id}/coins` | POST | admin | Add to or set a user's coin balance |
| `/sync/{platform}` | POST | approved | Generate a one-time code to link Discord or Telegram |
| `/platforms` | GET | none | Static list of linkable platforms |
| `/admin/users/pending` | GET | admin | List accounts awaiting approval |
| `/admin/users/{id}/review` | POST | admin | Approve or reject a pending account |
| `/admin/platforms` | GET | admin | Static list of all platforms this deployment supports |
| `/health` | GET | none | Liveness check; also reports whether an AI provider is configured |

"owner" above means the route additionally verifies the requested `chat_id` belongs to the caller's own `nebula_user_id` — a mismatch (someone else's chat, or a nonexistent id) returns `404`, deliberately not `403`, so existence of another user's chat is never revealed.

### Chat & Multi-Chat Memory

See "Memory Management" above for the chat-scoping mechanics. From the API's perspective: `POST /chat` creates a new, empty chat (its own 200k-token budget starts fresh); `POST /chat/{id}/messages` is the only way to actually converse — `GET /chat/{id}` is read-only history. There is no separate `/ai/generate` endpoint; everything chat-related lives under `/chat/{id}/...` (a deliberate simplification confirmed for this release, versus an earlier draft spec that had `/ai/generate` as a sibling).

### Image Uploads (Multimodal)

`POST /chat/{id}/messages/image` accepts `multipart/form-data` with an `image` file field (`image/jpeg`, `image/png`, `image/gif`, or `image/webp`, max 10MB) and an optional `text` query/form field as an accompanying caption. The image is forwarded to the AI provider as real multimodal content — see "AI Provider Abstraction" above — not merely noted as an attachment the way Discord/Telegram currently handle images.

### Tool Toggling

`POST /chat/{id}/messages` accepts an optional `"tools": {"search": true|false}` in its JSON body (defaults to `true`, i.e. unchanged availability) to let a user disable Nebula's ability to search the web for that one message.

## Google OAuth (Infrastructure)

`GET /api/v1/auth/google` redirects to Google's consent screen; `GET /api/v1/auth/google/callback` exchanges the returned code for tokens, looks up (or creates) a Nebula account keyed on the Google account's verified email, stores the tokens **encrypted** in `oauth_connections`, and issues a normal app JWT.

- Encryption: `cryptography`'s Fernet, via `core/crypto.py`'s `TokenCipher`, keyed from `OAUTH_TOKEN_ENCRYPTION_KEY`. This is genuine two-way encryption (not hashing) since the tokens must eventually be presented to Google's APIs in plaintext.
- Nothing in Nebula requires this to be configured. Every other feature — signup, login, chat, platform linking — works with these env vars left blank; hitting the Google OAuth routes without them configured returns a clear `503`.
- No Google Sheets/Calendar tool consumes these stored tokens yet — this release only gets tokens safely into `oauth_connections`. Building an actual tool on top of this is future work.

## Database Structure

See README.md's Database Schema table for the full list. Everything hangs off `nebula_user_id` (from `nebula_users`); `platform_identities` is the only table that knows about specific platform user IDs (including web sessions and Google-linked identities). Two tables are new in 1.5.0:

- **`chats`**: `chat_id` (PK), `nebula_user_id` (FK), `title`, `created_at`, `last_message_at`. One row per web chat; Discord/Telegram never create rows here.
- **`oauth_connections`**: `nebula_user_id` (FK), `provider`, `access_token`/`refresh_token` (both encrypted), `expires_at`, `scopes`, timestamps. One row per `(nebula_user_id, provider)` pair — reconnecting a provider updates the existing row.

`conversation_history` gained a nullable `chat_id` column (FK → `chats.chat_id`): `NULL` = the legacy Discord/Telegram account-wide history (untouched by this migration, including every pre-existing row); a real value scopes a message to one web chat. Existing databases auto-migrate this column in via `ALTER TABLE` on first startup after upgrading — no manual SQL needed, no data loss, no backfill required (see MIGRATION_GUIDE.md).

## Best Practices

### Security
1. Never commit API keys, `.env`, `JWT_SECRET`, or `OAUTH_TOKEN_ENCRYPTION_KEY` to version control.
2. Treat `ADMIN_BOOTSTRAP_KEY`, `JWT_SECRET`, and `OAUTH_TOKEN_ENCRYPTION_KEY` like root passwords — long, random, used carefully, never shared.
3. On Telegram, `/signup` and `/login` necessarily put a password in the chat's own message history — Nebula shows a clear warning after each of these telling you to delete that message yourself. Discord avoids this via ephemeral slash command parameters; the web panel avoids it entirely since passwords travel over HTTPS in a request body, never rendered into any persisted chat log.
4. Sync codes (`/sync` → `/verify`, from Discord or web) expire after 10 minutes and are single-use.
5. Losing `OAUTH_TOKEN_ENCRYPTION_KEY` permanently loses the ability to decrypt already-stored Google tokens — acceptable, since a user can simply reconnect Google, but avoid losing it carelessly regardless.

### Performance
1. Prefer the model-driven natural-language interface over direct commands where both exist.
2. Monitor memory via `/memory_stats` (Discord/Telegram) — on web, each chat's own capacity is implicit in how much history it can hold before needing a new chat.
3. Check `/admin_logs` for an audit trail across every platform, including web.

---

For more information, see README.md or CHANGELOG.md.
