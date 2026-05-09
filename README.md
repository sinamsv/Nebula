# Nebula - AI-Powered Discord Admin Bot

![Python Version](https://img.shields.io/badge/python-3.9+-blue)
![Discord.py](https://img.shields.io/badge/discord.py-2.3+-blue)
[![Documentation](https://img.shields.io/badge/Docs-Documentation-blue)](./DOCUMENTATION.md)
[![Migration](https://img.shields.io/badge/Guide-Migration-orange)](./MIGRATION_GUIDE.md)
[![License](https://img.shields.io/badge/License-MIT-green)](./LICENSE.txt)


Nebula is an advanced AI-powered Discord bot built with Python and discord.py, featuring conversational AI capabilities, memory management, and comprehensive admin tools.

## ✨ Features

### 🤖 AI-Powered Conversations
- Natural language processing using OpenAI's GPT models
- Context-aware responses that remember previous conversations
- Addresses users by their display names for personal engagement
- Handles replies to messages intelligently

### 💾 Memory Management
- SQLite database for conversation history
- 400,000 token memory capacity
- Automatic memory reset when limit is reached
- Tracks individual users while maintaining shared conversation context

### 🔍 Web Search Integration
- Google Custom Search API integration
- Available to all users (when explicitly requested)
- Returns formatted search results with links

### 🛡️ Admin Tools (Administrator-Only)
- **Kick User**: Remove members from the server
- **Ban User**: Permanently ban members
- **Create Channel**: Create text or voice channels in specified categories
- **User Activity Check**: View detailed user activity statistics
- **Admin Logs**: Track all moderation actions

### 📊 Features
- Automatic message splitting for long responses (>2000 characters)
- Image attachment detection
- Reply context awareness
- Comprehensive logging system

## 📋 Prerequisites

- Python 3.9 or higher
- Discord Bot Token
- OpenAI API Key (Note: This bot uses OpenAI library version 1.12.0+)
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
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_BASE_URL=  # Optional: leave empty for default OpenAI endpoint
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

#### OpenAI API Key:
1. Go to [OpenAI Platform](https://platform.openai.com/api-keys)
2. Create a new API key
3. Copy the key (you won't be able to see it again)

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

Simply mention the bot in any message:

```
@Nebula what's the weather like?
@Nebula can you help me understand this concept?
```

### Replying to Messages

Nebula understands context when you mention it in a reply:

```
[Reply to a message] @Nebula can you explain this?
```

### Web Search

Ask Nebula to search for information:

```
@Nebula search for the latest AI news
@Nebula can you search "Python best practices"
```

### Admin Commands (Administrators Only)

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

#### View Memory Stats
```
!memory_stats
```

#### View Admin Logs
```
!admin_logs 20
```

#### Reset Conversation Memory
```
!reset_memory
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
│   └── memory_manager.py # Memory and token management
└── nebula.db            # SQLite database (created on first run)
```

## 🗄️ Database Schema

### conversation_history
Stores all conversation messages with token counts.

### user_profiles
Tracks user information and activity statistics.

### server_settings
Stores server-specific configuration.

### admin_actions_log
Logs all administrative actions for audit purposes.

## ⚙️ Configuration

### Memory Management
- **Max Tokens**: 400,000 tokens
- **Auto-Reset**: Automatically resets when limit is reached
- **Token Counting**: Uses tiktoken for accurate GPT-4 token counting

### OpenAI Configuration
- **Library Version**: OpenAI >= 1.12.0 (uses new AsyncOpenAI client)
- **Default Model**: gemini-2.0-flash
- **Temperature**: 0.7
- **Max Tokens**: 2000 per response
- **Custom Base URL**: Supports OpenAI-compatible APIs (e.g., Liara.ir, Azure OpenAI)

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

## 🐛 Troubleshooting

### Bot doesn't respond
- Check if bot is online
- Verify bot has permission to read and send messages
- Ensure Message Content Intent is enabled
- Check if bot was properly mentioned (@Nebula)

### Memory issues
- Check token usage with `!memory_stats`
- Reset memory if needed with `!reset_memory`
- Verify database file exists and is writable

### API errors
- Verify all API keys are correct in `.env`
- Check OpenAI account has credits
- Ensure Google Search API is enabled and configured

### Search not working
- Verify Google Search API credentials
- Check if search quota is exceeded
- Ensure Custom Search Engine is properly configured

## 📝 Development

### Adding New Features

1. Create a new cog in the `cogs/` directory
2. Implement commands and event listeners
3. Load the cog in `bot.py`

### Adding New AI Tools

1. Add tool definition in `ai_handler.py` → `get_available_tools()`
2. Implement tool execution in `execute_tool()`
3. Add corresponding method in appropriate cog

## 🤝 Contributing

Contributions are welcome! Please feel free to submit pull requests or open issues for bugs and feature requests.

## 📄 License

MIT License

## ⚠️ Important Notes

- Keep your API keys secure and never commit them to version control
- Monitor your OpenAI API usage to avoid unexpected costs
- Regularly check admin logs for security auditing
- Back up the database file periodically
- Respect Discord's API rate limits and terms of service

## 🆘 Support

If you encounter any issues:
1. Check the console logs for error messages
2. Verify all environment variables are set correctly
3. Ensure all dependencies are installed
4. Check Discord bot permissions
5. Review the troubleshooting section above

## 🎉 Getting Started Checklist

- [ ] Python 3.9+ installed
- [ ] All dependencies installed (`pip install -r requirements.txt`)
- [ ] `.env` file created with all required tokens
- [ ] Discord bot created with proper intents enabled
- [ ] Bot invited to your Discord server with correct permissions
- [ ] `system.txt` customized (optional)
- [ ] Bot running (`python bot.py`)
- [ ] Test message sent to bot

---

**Enjoy using Nebula! 🌟**
