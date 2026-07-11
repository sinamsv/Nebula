import tiktoken
from typing import List, Dict, Optional
from core.database import DatabaseManager


class MemoryManager:
    """Platform-agnostic conversation memory, scoped to nebula_user_id.

    Unlike the old per-channel scheme (which auto-reset on overflow),
    this cap is a hard stop: once a user's stored history reaches
    MAX_TOKENS, new AI messages are refused with an explicit message
    telling them to run /memory_reset. This matches the project's
    "explicit failure over silent fallback" principle — silently wiping
    someone's cross-platform memory without them asking for it would be
    a worse surprise than telling them it's full.
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

    def get_usage(self, nebula_user_id: int) -> Dict:
        total_tokens = self.db.get_total_tokens(nebula_user_id)
        percentage = (total_tokens / self.MAX_TOKENS) * 100 if self.MAX_TOKENS else 0
        return {
            'total_tokens': total_tokens,
            'max_tokens': self.MAX_TOKENS,
            'percentage': round(percentage, 2),
            'remaining': max(0, self.MAX_TOKENS - total_tokens),
            'is_full': total_tokens >= self.MAX_TOKENS,
        }

    def is_full(self, nebula_user_id: int) -> bool:
        return self.db.get_total_tokens(nebula_user_id) >= self.MAX_TOKENS

    async def add_message_to_memory(self, nebula_user_id: int, role: str,
                                     content: str, source_platform: str) -> Dict:
        """Store a message. Returns the usage dict AFTER storing, so
        callers can warn the user if they just crossed the threshold.

        Deliberately does NOT block storage of the message being added
        here — the block happens earlier, before generating the AI
        response (see AIHandler), so a user's own outgoing message and
        the assistant's reply to it are still saved even if that reply
        is the one that pushes past the cap. What's blocked is starting
        a NEW turn once already full.
        """
        token_count = self.count_tokens(content)
        self.db.add_message(nebula_user_id, role, content, source_platform, token_count)
        return self.get_usage(nebula_user_id)

    def get_conversation_context(self, nebula_user_id: int, max_messages: int = 50) -> List[Dict]:
        """Retrieve conversation context formatted for the OpenAI-compatible
        API. Cross-platform: this pulls the user's full history regardless
        of which platform each message originated on, which is the whole
        point of the per-user memory model. We tag the origin platform
        inline so the model has context if it's relevant (e.g. "you said
        this on Telegram earlier"), without it being load-bearing."""
        history = self.db.get_conversation_history(nebula_user_id, max_messages)
        formatted = []
        for msg in history:
            if msg['role'] == 'user':
                content = msg['content']
            else:
                content = msg['content']
            formatted.append({"role": msg['role'], "content": content})
        return formatted

    def reset_memory(self, nebula_user_id: int):
        self.db.reset_conversation(nebula_user_id)

    def full_memory_message(self, display_name: str) -> str:
        return (
            f"⚠️ {display_name}, your Nebula memory is full "
            f"({self.MAX_TOKENS:,} token limit reached). "
            f"Run `/memory_reset` to clear it and keep chatting, or your "
            f"conversation history will stop growing until you do."
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
