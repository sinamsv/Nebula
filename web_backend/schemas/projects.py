from typing import List, Dict, Any, Optional
from pydantic import BaseModel
from web_backend.schemas.chat import ToolToggles

class ProjectCreateRequest(BaseModel):
    name: str
    description: Optional[str] = ""

class ProjectMetadataResponse(BaseModel):
    id: str
    name: str
    description: str
    owner: str
    created_at: str
    updated_at: str
    pinned: bool

class ProjectDetailResponse(BaseModel):
    id: str
    name: str
    description: str
    owner: str
    created_at: str
    updated_at: str
    pinned: bool
    instruction: str
    files: List[str]

class ProjectUpdateRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    pinned: Optional[bool] = None

class ProjectListResponse(BaseModel):
    projects: List[ProjectMetadataResponse]

class ProjectChatSummary(BaseModel):
    chat_id: str
    title: str
    created_at: str
    last_message_at: str

class ProjectChatListResponse(BaseModel):
    chats: List[ProjectChatSummary]

class ProjectCreateChatRequest(BaseModel):
    title: Optional[str] = "New Chat"

class ProjectChatMessage(BaseModel):
    role: str
    content: str
    timestamp: str

class ProjectChatHistoryResponse(BaseModel):
    chat_id: str
    title: str
    messages: List[ProjectChatMessage]

class ProjectSendMessageRequest(BaseModel):
    input: str
    tools: ToolToggles = ToolToggles()
    model: Optional[str] = None

class ProjectSendMessageResponse(BaseModel):
    reply_text: Optional[str]
    tool_messages: List[str]
    memory_warning: Optional[str]
    usage: Dict[str, Any]
