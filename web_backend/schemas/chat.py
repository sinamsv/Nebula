"""Pydantic schemas for /chat/* routes."""
from typing import Dict, List, Optional

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
    (e.g. {"search": true}) -- currently only "search" is a real
    toggle-able tool (moderation tools are never offered on web at all,
    same as Telegram, since handle_turn() is never given a
    discord_guild here). Extra keys are ignored rather than rejected,
    so adding a new toggle later doesn't require a frontend/backend
    version lockstep."""
    search: bool = True

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
