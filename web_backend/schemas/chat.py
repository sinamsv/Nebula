"""Pydantic schemas for /chat/* routes."""
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel


class ChatSummary(BaseModel):
    chat_id: int
    title: str
    created_at: str
    last_message_at: str


class ChatListResponse(BaseModel):
    chats: List[ChatSummary]


class CreateChatRequest(BaseModel):
    title: Optional[str] = "New Chat"


class ChatMessage(BaseModel):
    role: str
    content: str
    source_platform: str
    timestamp: str


class ChatHistoryResponse(BaseModel):
    chat_id: int
    title: str
    messages: List[ChatMessage]


class RenameChatRequest(BaseModel):
    title: str


class ToolToggles(BaseModel):
    """Matches the confirmed /ai/generate body shape's "tools" object
    (e.g. {"search": "smart"}).

    search is now a 3-state mode, not a bool (confirmed with Sina):
      - "off": search tool is never offered to the model this turn.
      - "smart" (default): search tool is offered; the model decides
        for itself when to use it, per system.txt's existing
        "only search when explicitly asked / when data is clearly
        stale" guidance -- this is exactly the old enable_search=True
        behavior, just given an explicit name.
      - "on": search tool is offered, AND an extra per-turn
        instruction is injected telling the model to actually use
        search if the message plausibly needs it, or -- if the
        message doesn't need search at all -- to tell the user their
        search mode is on but this message didn't need it, and
        suggest switching to smart/off. This is a prompt-level nudge,
        not a forced tool_choice, so a plain "hi" with search=on
        doesn't force a pointless search call.

    Currently "search" is the only real toggle-able tool (moderation
    tools are never offered on web at all, same as Telegram, since
    handle_turn() is never given a discord_guild here). Extra keys are
    ignored rather than rejected, so adding a new toggle later doesn't
    require a frontend/backend version lockstep.
    """
    search: Literal["on", "off", "smart"] = "smart"

    class Config:
        extra = "ignore"


class SendMessageRequest(BaseModel):
    input: str
    tools: ToolToggles = ToolToggles()


class SendMessageResponse(BaseModel):
    reply_text: Optional[str]
    tool_messages: List[str]
    memory_warning: Optional[str]
    usage: Dict
