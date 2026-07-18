import tiktoken
from typing import List, Dict, Optional
from core.database import DatabaseManager


class MemoryManager:
    """Platform-agnostic conversation memory, scoped to nebula_user_id
    (Discord/Telegram) or optionally to a specific web chat_id (web panel).

    Unlike the old per-channel scheme (which auto-reset on overflow),
    this cap is a hard stop: once a scope's stored history reaches
    MAX_TOKENS, new AI messages are refused with an explicit message
    telling them to reset it. This matches the project's "explicit
    failure over silent fallback" principle — silently wiping someone's
    memory without them asking for it would be a worse surprise than
    telling them it's full.

    --- Web panel addition: chat-scoped memory (confirmed with Sina) ---

    Every method below takes an optional `chat_id` parameter, default
    None:
      - chat_id=None: exactly the pre-existing behavior. Discord and
        Telegram never pass chat_id, so nothing about their behavior
        changes -- they keep sharing ONE 200k-token cap across the
        whole nebula_user_id, spanning both platforms, exactly as
        before this feature existed.
      - chat_id=<int>: scopes every operation to that one web chat.
        Confirmed with Sina: each web chat gets its OWN independent
        200k-token cap. It is NOT pooled with the account's Discord/
        Telegram cap, and NOT pooled with the account's other web
        chats -- a user with five web chats effectively has 5 x 200k
        of *additional* capacity on top of their one shared Discord/
        Telegram cap, not one 200k pool split five ways.

    This mirrors core/database.py's chat_id handling one level up --
    see that file's class docstring for the schema-level rationale.
    """

    MAX_TOKENS = 200_000

    def __init__(self, db: DatabaseManager):
        self.db = db
        self.encoding = tiktoken.encoding_for_model("gpt-4")

    def count_tokens(self, text: str) -> int:
        try:
            return len(self.encoding.encode(text))
        except Exception:
            # Fallback: rough estimate, matches old behavior.
            return len(text) // 4

    def get_usage(self, nebula_user_id: int, chat_id: Optional[int] = None) -> Dict:
        total_tokens = self.db.get_total_tokens(nebula_user_id, chat_id=chat_id)
        percentage = (total_tokens / self.MAX_TOKENS) * 100 if self.MAX_TOKENS else 0
        return {
            'total_tokens': total_tokens,
            'max_tokens': self.MAX_TOKENS,
            'percentage': round(percentage, 2),
            'remaining': max(0, self.MAX_TOKENS - total_tokens),
            'is_full': total_tokens >= self.MAX_TOKENS,
        }

    def is_full(self, nebula_user_id: int, chat_id: Optional[int] = None) -> bool:
        return self.db.get_total_tokens(nebula_user_id, chat_id=chat_id) >= self.MAX_TOKENS

    async def add_message_to_memory(self, nebula_user_id: int, role: str,
                                     content: str, source_platform: str,
                                     chat_id: Optional[int] = None) -> Dict:
        """Store a message. Returns the usage dict AFTER storing, so
        callers can warn the user if they just crossed the threshold.

        Deliberately does NOT block storage of the message being added
        here — the block happens earlier, before generating the AI
        response (see AIHandler), so a user's own outgoing message and
        the assistant's reply to it are still saved even if that reply
        is the one that pushes past the cap. What's blocked is starting
        a NEW turn once already full (in that scope).
        """
        token_count = self.count_tokens(content)
        self.db.add_message(nebula_user_id, role, content, source_platform, token_count, chat_id=chat_id)
        return self.get_usage(nebula_user_id, chat_id=chat_id)

    def get_conversation_context(self, nebula_user_id: int, max_messages: int = 50,
                                  chat_id: Optional[int] = None) -> List[Dict]:
        """Retrieve conversation context formatted for the provider-
        agnostic API. Cross-platform when chat_id=None: pulls the
        user's full Discord/Telegram history regardless of which
        platform each message originated on. When chat_id is given,
        pulls only that web chat's own history instead -- web chats are
        deliberately NOT merged with the Discord/Telegram history or
        with each other."""
        history = self.db.get_conversation_history(nebula_user_id, max_messages, chat_id=chat_id)
        formatted = []
        for msg in history:
            formatted.append({"role": msg['role'], "content": msg['content']})
        return formatted

    def reset_memory(self, nebula_user_id: int, chat_id: Optional[int] = None):
        self.db.reset_conversation(nebula_user_id, chat_id=chat_id)

    def full_memory_message(self, display_name: str) -> str:
        return (
            f"⚠️ {display_name}, your Nebula memory is full "
            f"({self.MAX_TOKENS:,} token limit reached). "
            f"Run `/memory_reset` to clear it and keep chatting, or your "
            f"conversation history will stop growing until you do."
        )

    def full_chat_memory_message(self, display_name: str, chat_title: str) -> str:
        """Web-specific variant of full_memory_message(): points at
        clearing/starting a new chat rather than a slash command, since
        the web UI has no /memory_reset command."""
        return (
            f"⚠️ {display_name}, this chat (\"{chat_title}\") has reached its "
            f"{self.MAX_TOKENS:,} token limit. Start a new chat to keep "
            f"talking to Nebula, or clear this chat's history."
        )

    def approaching_full_warning(self, usage: Dict) -> Optional[str]:
        """Optional soft warning at 90% capacity, returned alongside a
        normal response rather than blocking it. Returns None if not
        close to full yet."""
        if usage['percentage'] >= 90 and not usage['is_full']:
            return (
                f"💾 Heads up — your Nebula memory is at {usage['percentage']}% "
                f"capacity. Run `/memory_reset` when you'd like to clear it."
            )
        return None
