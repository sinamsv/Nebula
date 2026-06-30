# Nebula - AI-Powered Discord Admin Bot

![Python Version](https://img.shields.io/badge/python-3.9+-blue)
![Discord.py](https://img.shields.io/badge/discord.py-2.3+-blue)
[![Documentation](https://img.shields.io/badge/Docs-Documentation-blue)](./DOCUMENTATION.md)
[![Migration](https://img.shields.io/badge/Guide-Migration-orange)](./MIGRATION_GUIDE.md)
[![License](https://img.shields.io/badge/License-MIT-green)](./LICENSE.txt)


Nebula is an advanced AI-powered Discord bot built with Python and discord.py, featuring conversational AI capabilities, memory management, and comprehensive admin tools. Now fully migrated to Slash Commands for a modern, seamless experience.

## ✨ Features

### 🤖 AI-Powered Conversations
- Natural language processing using **gemini-3.1-flash-lite**
- High efficiency with near-zero hallucination rates
- Context-aware responses that remember previous conversations
- Addresses users by their display names for personal engagement
- Handles replies to messages intelligently

### 💾 Memory Management
- SQLite database for conversation history
- 400,000 token memory capacity
- Automatic memory reset when limit is reached
- Tracks individual users while maintaining shared conversation context
- Admin commands for monitoring and resetting memory

### 🌝 Nebula Coin System (Rate Limiting)
An elegant rate-limiting system designed to prevent spam and optimize hosting costs:
- **Starting Balance**: Every user starts with **10 coins** per guild.
- **Consumption**:
  - **1 coin** per AI message response.
  - **2 coins** per web search.
- **Automatic Reset**: Balance resets back to 10 (does not stack) every **8 hours**.
- **Transparency**: Users can check their budget at any time.
- **Admin Control**: Administrators can manually grant or set coin balances for users.

### 🔍 Web Search Integration
- Google Custom Search API integration
- Available to all users (costs 2 Nebula Coins)
- Returns formatted search results with links

### 🛡️ Admin Tools (Administrator-Only)
- **Kick User**: Remove members from the server via AI request
- **Ban User**: Permanently ban members via AI request
- **Create Channel**: Create text or voice channels in specified categories via AI request
- **User Activity Check**: View detailed user activity statistics
- **Admin Logs**: Track all moderation actions via `/admin_logs`
- **Resource Control**: Manage server resource consumption via the Coin System

### 📊 Features
- Automatic message splitting for long responses (>2000 characters)
- Image attachment detection
- Reply context awareness
- Comprehensive logging system
- Full Slash Command support

## 📋 Prerequisites

- Python 3.9 or higher
- Discord Bot Token
- OpenAI-compatible API Key (e.g., Google AI Studio, OpenAI, Liara.ir)
- Google Custom Search API Key (optional, for search functionality)

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

2. Edit `.env` and fill in your credentials:

```env
DISCORD_TOKEN=your_discord_bot_token_here
OPENAI_API_KEY=your_api_key_here
OPENAI_BASE_URL=  # Optional: e.g., https://generativelanguage.googleapis.com/v1beta/openai/
AI_MODEL=google/gemini-3.1-flash-lite
GOOGLE_SEARCH_API_KEY=your_google_search_api_key_here
GOOGLE_SEARCH_ENGINE_ID=your_search_engine_id_here
```

### 4. Get Your API Keys

#### Discord Bot Token:
1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Create a new application
3. Go to the "Bot" section
4. Click "Reset Token" and copy your bot token
5. Enable these Privileged Gateway Intents:
   - Server Members Intent
   - Message Content Intent

#### AI API Key (Gemini):
1. Go to [Google AI Studio](https://aistudio.google.com/)
2. Create a new API key
3. Copy the key into `OPENAI_API_KEY` in `.env`
4. Set `OPENAI_BASE_URL` to `https://generativelanguage.googleapis.com/v1beta/openai/`

#### Google Custom Search (Optional):
1. Get API Key: [Google Cloud Console](https://console.cloud.google.com/apis/credentials)
2. Get Search Engine ID: [Programmable Search Engine](https://programmablesearchengine.google.com/)

### 5. Customize System Prompt (Optional)

Edit `system.txt` to customize Nebula's personality and behavior.

### 6. Run the Bot

```bash
python bot.py
```

## 🎯 Usage

### Talking to Nebula

Simply mention the bot in any message to start a conversation:

```
@Nebula what's the weather like?
@Nebula can you help me understand this concept?
```

Nebula also understands context when you mention it in a reply:
```
[Reply to a message] @Nebula can you explain this?
```
*Note: Each response costs 1 Nebula Coin.*

### Web Search

Ask Nebula to search for information:
```
@Nebula search for the latest AI news
```
Or use the direct slash command:
```
/search query: Python best practices
```
*Note: Each search costs 2 Nebula Coins.*

### Slash Commands

#### For Users
- `/coin`: Show your current Nebula Coin balance and time until reset.
- `/search query:<text>`: Perform a web search using Google Custom Search.

#### For Administrators Only
- `/add_coin member:@user amount:<number> mode:<add|set>`: Modify a user's Nebula Coin balance.
- `/admin_logs limit:<number>`: View recent administrative action logs.
- `/memory_stats`: Show memory usage statistics for the current channel.
- `/reset_memory`: Clear conversation memory for the current channel.

### AI-Powered Admin Tools (Administrators Only)

You can perform moderation tasks by simply asking Nebula while mentioning it:

#### Kick a User
```
@Nebula kick @username for spamming
```

#### Ban a User
```
@Nebula ban @username for violating rules
```

#### Create a Channel
```
@Nebula create a text channel called "general-chat" in the "Community" category
```

#### Check User Activity
```
@Nebula check activity for @username
```

## 🏗️ Project Structure

```
nebula-bot/
├── bot.py                 # Main bot file
├── database.py            # Database management
├── system.txt            # AI system prompt
├── requirements.txt      # Python dependencies
├── .env.sample          # Environment variables template
├── cogs/
│   ├── ai_handler.py    # AI message processing
│   ├── admin_tools.py   # Admin moderation tools
│   ├── search_tool.py   # Google Search integration
│   ├── memory_manager.py # Memory and token management
│   └── coin_manager.py   # Nebula Coin system
└── nebula.db            # SQLite database (created on first run)
```

## 🗄️ Database Schema

### conversation_history
Stores all conversation messages with token counts.

### user_profiles
Tracks user information and activity statistics.

### coin_balances
Tracks user coin balances and reset timestamps per guild.

### server_settings
Stores server-specific configuration.

### admin_actions_log
Logs all administrative actions for audit purposes.

## ⚙️ Configuration

### Memory Management
- **Max Tokens**: 400,000 tokens
- **Auto-Reset**: Automatically resets when limit is reached
- **Token Counting**: Uses tiktoken for accurate token counting

### AI Configuration
- **Model**: google/gemini-3.1-flash-lite (Recommended for efficiency and accuracy)
- **Temperature**: 0.7
- **Max Tokens**: 2000 per response
- **Custom Base URL**: Supports OpenAI-compatible APIs

### Message Handling
- **Max Message Length**: 2000 characters (Discord limit)
- **Auto-Split**: Long messages are automatically split
- **Reply Context**: Includes replied-to messages in context

## 🔒 Permissions Required

The bot needs the following Discord permissions:
- Read Messages/View Channels
- Send Messages
- Manage Messages
- Embed Links
- Read Message History
- Mention Everyone (for admin tools)
- Kick Members (for kick tool)
- Ban Members (for ban tool)
- Manage Channels (for create channel tool)

## 🤝 Contributing

Contributions are welcome! Please feel free to submit pull requests or open issues for bugs and feature requests.

## 📄 License

MIT License

---

**Enjoy using Nebula! 🌟**
