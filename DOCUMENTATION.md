# Nebula Bot - Detailed Documentation

## Table of Contents
1. [Architecture Overview](#architecture-overview)
2. [AI System](#ai-system)
3. [Memory Management](#memory-management)
4. [Nebula Coin System](#nebula-coin-system)
5. [Admin Tools](#admin-tools)
6. [Search Functionality](#search-functionality)
7. [Database Structure](#database-structure)
8. [API Integration](#api-integration)
9. [Best Practices](#best-practices)

## Architecture Overview

Nebula follows a modular architecture using Discord.py's cog system:

```
Bot Core (bot.py)
    ├── Memory Manager Cog
    ├── Coin Manager Cog
    ├── AI Handler Cog
    ├── Admin Tools Cog
    └── Search Tool Cog
           ↓
    Database Layer (database.py)
           ↓
    SQLite Database (nebula.db)
```

### Component Responsibilities

- **bot.py**: Main entry point, loads cogs, handles Discord connection, and syncs Slash Commands.
- **database.py**: Database abstraction layer for all data operations.
- **ai_handler.py**: Processes messages, calls AI API, manages tool execution.
- **coin_manager.py**: Manages the Nebula Coin rate-limiting system.
- **memory_manager.py**: Handles conversation memory and token tracking.
- **admin_tools.py**: Implements moderation commands and slash commands for admins.
- **search_tool.py**: Google Custom Search integration and slash command.

## AI System

### Message Processing Flow

1. **Message Received** → Bot checks if it's mentioned.
2. **Coin Check** → Verifies if the user has enough Nebula Coins.
3. **Context Gathering** → Retrieves reply context if applicable.
4. **Memory Retrieval** → Loads recent conversation history.
5. **AI Processing** → Sends to AI model (Gemini 3.1 Flash Lite recommended) with available tools.
6. **Tool Execution** → Executes any requested tool calls (e.g., search, kick).
7. **Response Generation** → Formats and sends response.
8. **Memory Storage** → Saves conversation to database.

### System Prompt

The system prompt (`system.txt`) defines Nebula's personality and capabilities. Key elements:

- **Identity**: Friendly AI admin bot.
- **Behavior**: Personal, addressing users by name.
- **Capabilities**: Lists available tools and features.
- **Guidelines**: Rules for tool usage and interaction.

### Tool System

Tools are defined in OpenAI's function calling format and are compatible with Gemini and other modern models:

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

Available tools are dynamically determined based on user permissions.

### Context Window Management

- Maximum context: Limited by the model's context window.
- History retrieval: Last 50 messages by default.
- Token counting: Uses tiktoken for accurate token counts.
- Automatic truncation: Older messages dropped when limit reached (400k default).

## Memory Management

### Token Tracking

```python
# Token counting
def count_tokens(text: str) -> int:
    encoding = tiktoken.encoding_for_model("gpt-4")
    return len(encoding.encode(text))
```

### Memory Lifecycle

1. **Message Arrives** → Count tokens.
2. **Check Limit** → Compare with 400k token limit.
3. **Reset if Needed** → Clear history if limit exceeded.
4. **Store Message** → Save to database with token count.
5. **Update Profile** → Update user statistics.

### Memory Commands (Admin Only)

- `/memory_stats`: View current token usage and percentage of capacity used.
- `/reset_memory`: Clear conversation history for the current channel.

### Automatic Reset

When total tokens exceed 400,000:
- Entire conversation history is cleared for the channel.
- Fresh start with next message.
- User profiles and admin logs are preserved.

## Nebula Coin System

The Nebula Coin system provides a fair and transparent rate-limiting mechanism.

### Rules
- **Starting Balance**: 10 coins.
- **Message Cost**: 1 coin.
- **Search Cost**: 2 coins.
- **Reset Period**: 8 hours since the last reset point.
- **Reset Type**: Reset to 10 (non-stacking).

### Commands
- `/coin`: Check your current balance and time remaining until reset.
- `/add_coin [member] [amount] [mode:add|set]`: (Admin Only) Manually adjust a user's balance.

## Admin Tools

### User Moderation (AI-Powered)

Administrators can perform moderation actions by simply asking Nebula while mentioning it.

#### Kick User
```
@Nebula kick @username reason here
```

**Process:**
1. Verify admin permissions.
2. Parse user mention/ID.
3. Check bot's role hierarchy.
4. Execute kick.
5. Log action to database.
6. Confirm to admin.

#### Ban User
```
@Nebula ban @username reason here
```

**Process:**
1. Verify admin permissions.
2. Parse user mention/ID.
3. Check bot's role hierarchy.
4. Execute ban.
5. Log action to database.
6. Confirm to admin.

### Channel Management (AI-Powered)

#### Create Channel
```
@Nebula create a text channel called "new-channel" in "Category Name"
```

**Supported Types:**
- Text channels
- Voice channels

### User Activity (AI-Powered)

#### Activity Check
```
@Nebula check activity for @username
```

**Returns:**
- User ID, First seen, Last seen, Total message count, and Messages in last 7 days.

### Admin Logging

All administrative actions are logged. View logs with: `/admin_logs [limit]`

## Search Functionality

### Google Custom Search Integration

#### Usage
- **AI Tool**: Ask Nebula to "search for X" while mentioning it.
- **Slash Command**: Use `/search query:X`.

**Search Process:**
1. User requests search (costs 2 Coins).
2. Query sent to Google Custom Search API.
3. Results formatted (title, snippet, URL).
4. Response sent to user.

## Database Structure

### Tables

#### conversation_history
Stores all conversation messages.

#### user_profiles
Tracks user information and statistics.

#### coin_balances
Tracks user Nebula Coin balances and reset timers.

#### server_settings
Stores server-specific configuration.

#### admin_actions_log
Logs all administrative actions.

## API Integration

### AI API (OpenAI-Compatible)

Nebula uses the `AsyncOpenAI` client, making it compatible with OpenAI, Google Gemini, and various third-party providers.

#### Recommended Model
- `google/gemini-3.1-flash-lite`: Highly accurate, efficient, and cost-effective.

### Google Custom Search API

Requires `GOOGLE_SEARCH_API_KEY` and `GOOGLE_SEARCH_ENGINE_ID`.

## Best Practices

### Security
1. **Never commit API keys** to version control.
2. **Use .env files** for sensitive configuration.
3. **Validate user permissions** before admin actions.

### Performance
1. **Use Slash Commands** for direct interactions.
2. **Monitor token usage** via `/memory_stats`.
3. **Check admin logs** for audit trails.

---

For more information, see README.md or CHANGELOG.md.
