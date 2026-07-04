import discord
from discord.ext import commands
from openai import AsyncOpenAI
import os
import json
from typing import List, Dict

class AIHandler(commands.Cog):
    """Handles AI-powered message responses using OpenAI."""

    def __init__(self, bot):
        self.bot = bot
        self.openai_client = None
        self.setup_openai()
        self.load_system_prompt()

        # Get memory manager, admin tools, coin manager (loaded lazily)
        self.memory_manager = None
        self.admin_tools = None
        self.coin_manager = None

    def setup_openai(self):
        """Configure OpenAI client using new AsyncOpenAI structure."""
        api_key = os.getenv('OPENAI_API_KEY')
        base_url = os.getenv('OPENAI_BASE_URL')


        if not api_key:
            print("WARNING: OPENAI_API_KEY not found!")
            return

        # Create AsyncOpenAI client with new structure (v1.0.0+)
        if base_url:
            self.openai_client = AsyncOpenAI(
                api_key=api_key,
                base_url=base_url
            )
            print(f"Using custom OpenAI base URL: {base_url}")
        else:
            self.openai_client = AsyncOpenAI(api_key=api_key)
            print("Using default OpenAI endpoint")

    def load_system_prompt(self):
        """Load system prompt from system.txt file."""
        try:
            with open('system.txt', 'r', encoding='utf-8') as f:
                self.system_prompt = f.read().strip()
            print("System prompt loaded successfully")
        except FileNotFoundError:
            self.system_prompt = """You are Nebula, a friendly and helpful AI-powered Discord administration bot.

You remember users by their display names and address them personally for better engagement.

You can answer general questions, help with server-related queries, and assist administrators with moderation tasks.

When administrators need to perform actions like kicking, banning, creating channels, or checking user activity, you have tools available to help them. You should use these tools when appropriate based on the conversation context.

Always be respectful, helpful, and maintain a positive tone. You have access to the conversation history, so you can reference previous discussions."""
            print("WARNING: system.txt not found, using default system prompt")

    def get_available_tools(self, is_admin: bool) -> List[Dict]:
        """Get available tools based on user permissions."""
        tools = []

        # Search tool available to everyone
        tools.append({
            "type": "function",
            "function": {
                "name": "search",
                "description": "Search the web for current information. Only use when user explicitly asks to search for something.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "The search query"
                        }
                    },
                    "required": ["query"]
                }
            }
        })

        # Admin-only tools
        if is_admin:
            tools.extend([
                {
                    "type": "function",
                    "function": {
                        "name": "kick_user",
                        "description": "Kick a member from the server",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "user_mention": {
                                    "type": "string",
                                    "description": "The user mention (e.g., @username or user ID)"
                                },
                                "reason": {
                                    "type": "string",
                                    "description": "Reason for kicking the user"
                                }
                            },
                            "required": ["user_mention", "reason"]
                        }
                    }
                },
                {
                    "type": "function",
                    "function": {
                        "name": "ban_user",
                        "description": "Ban a member from the server",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "user_mention": {
                                    "type": "string",
                                    "description": "The user mention (e.g., @username or user ID)"
                                },
                                "reason": {
                                    "type": "string",
                                    "description": "Reason for banning the user"
                                }
                            },
                            "required": ["user_mention", "reason"]
                        }
                    }
                },
                {
                    "type": "function",
                    "function": {
                        "name": "create_channel",
                        "description": "Create a new channel in the server",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "channel_name": {
                                    "type": "string",
                                    "description": "Name of the channel to create"
                                },
                                "category_name": {
                                    "type": "string",
                                    "description": "Name of the category to create channel in (optional)"
                                },
                                "channel_type": {
                                    "type": "string",
                                    "enum": ["text", "voice"],
                                    "description": "Type of channel: text or voice"
                                }
                            },
                            "required": ["channel_name", "channel_type"]
                        }
                    }
                },
                {
                    "type": "function",
                    "function": {
                        "name": "user_activity_check",
                        "description": "Check activity history of a specific user",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "user_mention": {
                                    "type": "string",
                                    "description": "The user mention (e.g., @username or user ID)"
                                }
                            },
                            "required": ["user_mention"]
                        }
                    }
                }
            ])

        return tools

    async def process_message(self, message: discord.Message, context_message: discord.Message = None):
        """Process a message and generate AI response."""
        # Get memory manager and coin manager if not already loaded
        if not self.memory_manager:
            self.memory_manager = self.bot.get_cog('MemoryManager')
        if not self.coin_manager:
            self.coin_manager = self.bot.get_cog('CoinManager')

        user_id = str(message.author.id)
        guild_id = str(message.guild.id)

        # --- Nebula Coin check: every AI message costs coins ---
        if self.coin_manager:
            spend_result = self.coin_manager.check_and_spend(
                user_id, guild_id, self.coin_manager.MESSAGE_COST
            )
            if not spend_result['success']:
                await message.channel.send(
                    self.coin_manager.insufficient_funds_message(
                        message.author.display_name,
                        spend_result['seconds_until_reset']
                    )
                )
                return

        # Build message content
        user_content = message.content.replace(f'<@{self.bot.user.id}>', '').strip()

        # If this is a reply, include the replied-to message
        if context_message:
            user_content = f"[Context - replying to message from {context_message.author.display_name}]: \"{context_message.content}\"\n\n{user_content}"

        # Check for images
        if message.attachments:
            image_urls = [att.url for att in message.attachments if att.content_type and att.content_type.startswith('image/')]
            if image_urls:
                user_content += f"\n\n[User attached {len(image_urls)} image(s)]"

        # Get conversation history
        conversation_history = self.memory_manager.get_conversation_context(message) if self.memory_manager else []

        # Check if user is admin
        is_admin = message.author.guild_permissions.administrator

        # Build messages for OpenAI
        messages = [
            {"role": "system", "content": self.system_prompt}
        ]
        messages.extend(conversation_history)
        messages.append({
            "role": "user",
            "content": f"[{message.author.display_name}]: {user_content}"
        })

        try:
            # Make OpenAI API call
            response = await self.call_openai(messages, is_admin)

            # Save user message to memory
            if self.memory_manager:
                await self.memory_manager.add_message_to_memory(message, "user", user_content)

            # Process response
            await self.handle_response(message, response)

        except Exception as e:
            print(f"Error processing message: {e}")
            await message.channel.send(f"Sorry {message.author.display_name}, I encountered an error processing your message. Please try again.")

    async def call_openai(self, messages: List[Dict], is_admin: bool):
        """Call OpenAI API using new client structure (v1.0.0+)."""
        if not self.openai_client:
            raise Exception("OpenAI client is not configured")

        tools = self.get_available_tools(is_admin)
        ai_model = os.getenv('AI_MODEL')
        # Use new AsyncOpenAI client structure
        response = await self.openai_client.chat.completions.create(
            model=ai_model,
            messages=messages,
            tools=tools if tools else None,
            tool_choice="auto" if tools else None,
            temperature=0.7,
            max_tokens=2000
        )

        return response

    async def handle_response(self, message: discord.Message, response):
        """Handle the AI response and execute any tool calls."""
        # Get the first choice from response
        choice = response.choices[0]
        response_message = choice.message

        # Check if there are tool calls (new structure uses tool_calls attribute)
        if response_message.tool_calls:
            for tool_call in response_message.tool_calls:
                function_name = tool_call.function.name
                function_args = json.loads(tool_call.function.arguments)

                # Execute the tool
                result = await self.execute_tool(message, function_name, function_args)

                # Send result message
                if result:
                    await message.channel.send(result)

        # Send the text response
        if response_message.content:
            response_text = response_message.content

            # Save assistant response to memory
            if self.memory_manager:
                await self.memory_manager.add_message_to_memory(message, "assistant", response_text)

            # Split long messages
            await self.send_long_message(message.channel, response_text)

    async def execute_tool(self, message: discord.Message, function_name: str, function_args: Dict) -> str:
        """Execute a tool function."""
        # Get admin tools / coin manager cogs if not already loaded
        if not self.admin_tools:
            self.admin_tools = self.bot.get_cog('AdminTools')
        if not self.coin_manager:
            self.coin_manager = self.bot.get_cog('CoinManager')

        search_tool = self.bot.get_cog('SearchTool')

        try:
            if function_name == "search" and search_tool:
                # --- Nebula Coin check: search costs extra coins ---
                if self.coin_manager:
                    user_id = str(message.author.id)
                    guild_id = str(message.guild.id)
                    spend_result = self.coin_manager.check_and_spend(
                        user_id, guild_id, self.coin_manager.SEARCH_COST
                    )
                    if not spend_result['success']:
                        return self.coin_manager.insufficient_funds_message(
                            message.author.display_name,
                            spend_result['seconds_until_reset']
                        )

                return await search_tool.perform_search(function_args.get('query'))

            elif function_name == "kick_user" and self.admin_tools:
                return await self.admin_tools.kick_user_tool(message, function_args.get('user_mention'), function_args.get('reason'))

            elif function_name == "ban_user" and self.admin_tools:
                return await self.admin_tools.ban_user_tool(message, function_args.get('user_mention'), function_args.get('reason'))

            elif function_name == "create_channel" and self.admin_tools:
                return await self.admin_tools.create_channel_tool(
                    message,
                    function_args.get('channel_name'),
                    function_args.get('category_name'),
                    function_args.get('channel_type')
                )

            elif function_name == "user_activity_check" and self.admin_tools:
                return await self.admin_tools.user_activity_tool(message, function_args.get('user_mention'))

            else:
                return f"Tool '{function_name}' not available or not implemented."

        except Exception as e:
            return f"Error executing tool '{function_name}': {str(e)}"

    async def send_long_message(self, channel, text: str):
        """Split and send long messages (>2000 characters)."""
        if len(text) <= 2000:
            await channel.send(text)
        else:
            # Split by paragraphs first
            chunks = []
            current_chunk = ""

            for line in text.split('\n'):
                if len(current_chunk) + len(line) + 1 <= 2000:
                    current_chunk += line + '\n'
                else:
                    if current_chunk:
                        chunks.append(current_chunk.strip())
                    current_chunk = line + '\n'

            if current_chunk:
                chunks.append(current_chunk.strip())

            # Send all chunks
            for i, chunk in enumerate(chunks):
                if i > 0:
                    chunk = f"*(continued)*\n{chunk}"
                await channel.send(chunk)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Listen for messages that mention the bot."""
        # Ignore bot's own messages
        if message.author == self.bot.user:
            return

        # Ignore DMs
        if not message.guild:
            return

        # Check if bot is mentioned
        if self.bot.user not in message.mentions:
            return

        # Check if this is a reply to another message
        context_message = None
        if message.reference and message.reference.message_id:
            try:
                context_message = await message.channel.fetch_message(message.reference.message_id)
            except:
                pass

        # Process the message
        await self.process_message(message, context_message)

async def setup(bot):
    """Setup function to load the cog."""
    await bot.add_cog(AIHandler(bot))
