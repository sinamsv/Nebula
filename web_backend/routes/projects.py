from typing import Optional
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status

from ai.handler import AIHandler
from core.database import DatabaseManager
from core.memory import MemoryManager
from web_backend.dependencies import (
    get_ai_handler,
    get_db,
    get_memory,
    require_approved_identity_web,
)
from web_backend.project_store import (
    ProjectStore,
    ProjectError,
    ProjectNotFoundError,
    ProjectPermissionError,
    ProjectValidationError,
    ProjectStorageError,
)
from web_backend.schemas.projects import (
    ProjectCreateRequest,
    ProjectMetadataResponse,
    ProjectListResponse,
    ProjectChatSummary,
    ProjectChatListResponse,
    ProjectCreateChatRequest,
    ProjectChatHistoryResponse,
    ProjectChatMessage,
    ProjectSendMessageRequest,
    ProjectSendMessageResponse,
)

router = APIRouter(prefix="/api/v1", tags=["projects"])


def _map_exceptions(func, *args, **kwargs):
    """Maps custom project exceptions to standard FastAPI HTTP exceptions to prevent info leaks."""
    try:
        return func(*args, **kwargs)
    except ProjectNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")
    except ProjectPermissionError:
        # Return 404 (not 403) to prevent leaking project existence to non-owners
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")
    except ProjectValidationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except ProjectStorageError as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Storage error: {str(e)}")
    except ProjectError as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/projects/{username}", response_model=ProjectListResponse)
async def list_user_projects(
    username: str,
    identity: dict = Depends(require_approved_identity_web),
):
    """Lists the authenticated user's projects. The username path parameter must match the authenticated user."""
    if identity["username"] != username:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied. You can only view your own projects.")

    store = ProjectStore()
    projects = _map_exceptions(store.list_projects, username)
    return ProjectListResponse(projects=[
        ProjectMetadataResponse(**p) for p in projects
    ])


@router.post("/projects/{username}", response_model=ProjectListResponse)
async def list_user_projects_post(
    username: str,
    identity: dict = Depends(require_approved_identity_web),
):
    """POST variant of user projects listing, implemented for compatibility / CLI stubbing."""
    if identity["username"] != username:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied. You can only view your own projects.")

    store = ProjectStore()
    projects = _map_exceptions(store.list_projects, username)
    return ProjectListResponse(projects=[
        ProjectMetadataResponse(**p) for p in projects
    ])


@router.post("/project/create", response_model=ProjectMetadataResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    body: ProjectCreateRequest,
    identity: dict = Depends(require_approved_identity_web),
):
    """Creates a new project for the authenticated user."""
    store = ProjectStore()
    project = _map_exceptions(store.create_project, body.name, body.description, identity["username"])
    return ProjectMetadataResponse(**project)


@router.delete("/project/delete/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: str,
    identity: dict = Depends(require_approved_identity_web),
):
    """Deletes the project folder and all contents for the authenticated owner."""
    store = ProjectStore()
    _map_exceptions(store.delete_project, identity["username"], project_id)


@router.post("/project/{project_id}/upload", response_model=ProjectMetadataResponse)
async def upload_project_assets(
    project_id: str,
    instruction: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
    identity: dict = Depends(require_approved_identity_web),
):
    """Handles updating project instructions (text) and/or uploading a knowledge file.

    At least one part must be provided, otherwise rejects with 400 Bad Request.
    """
    if instruction is None and file is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="At least 'instruction' or 'file' must be provided.")

    store = ProjectStore()
    # Verify existence and ownership first
    metadata = _map_exceptions(store.get_project_metadata, identity["username"], project_id)

    if instruction is not None:
        _map_exceptions(store.update_instruction, identity["username"], project_id, instruction)

    if file is not None:
        content_bytes = await file.read()
        _map_exceptions(store.save_knowledge_file, identity["username"], project_id, file.filename, content_bytes)

    # Re-fetch updated metadata with touched updated_at
    metadata = _map_exceptions(store.get_project_metadata, identity["username"], project_id)
    return ProjectMetadataResponse(**metadata)


@router.get("/project/{project_id}/chats", response_model=ProjectChatListResponse)
async def list_project_chats(
    project_id: str,
    identity: dict = Depends(require_approved_identity_web),
):
    """Lists chat threads belonging to this project. Owner-only."""
    store = ProjectStore()
    chats = _map_exceptions(store.list_chats, identity["username"], project_id)
    return ProjectChatListResponse(chats=[
        ProjectChatSummary(**c) for c in chats
    ])


@router.post("/project/{project_id}/chats", response_model=ProjectChatSummary, status_code=status.HTTP_201_CREATED)
async def create_project_chat(
    project_id: str,
    body: ProjectCreateChatRequest,
    identity: dict = Depends(require_approved_identity_web),
):
    """Creates a new chat thread scoped to this project. Owner-only."""
    store = ProjectStore()
    chat_data = _map_exceptions(store.create_chat, identity["username"], project_id, body.title)
    return ProjectChatSummary(
        chat_id=chat_data["chat_id"],
        title=chat_data["title"],
        created_at=chat_data["created_at"],
        last_message_at=chat_data["last_message_at"]
    )


@router.get("/project/{project_id}/chat/{chat_id}", response_model=ProjectChatHistoryResponse)
async def get_project_chat_history(
    project_id: str,
    chat_id: str,
    identity: dict = Depends(require_approved_identity_web),
):
    """Returns the message history of the specified project chat. Owner-only."""
    store = ProjectStore()
    chat_data = _map_exceptions(store.get_chat, identity["username"], project_id, chat_id)
    return ProjectChatHistoryResponse(
        chat_id=chat_data["chat_id"],
        title=chat_data["title"],
        messages=[
            ProjectChatMessage(
                role=m["role"],
                content=m["content"],
                timestamp=m["timestamp"]
            )
            for m in chat_data["messages"]
        ]
    )


@router.post("/project/{project_id}/chat/{chat_id}", response_model=ProjectSendMessageResponse)
async def send_project_chat_message(
    project_id: str,
    chat_id: str,
    body: ProjectSendMessageRequest,
    identity: dict = Depends(require_approved_identity_web),
    ai_handler: AIHandler = Depends(get_ai_handler),
    memory: MemoryManager = Depends(get_memory),
):
    """Sends a message into the project chat and gets a reply from the AI provider pipeline."""
    # Ensure the project exists and is owned by the user
    store = ProjectStore()
    _map_exceptions(store.get_project_metadata, identity["username"], project_id)
    _map_exceptions(store.get_chat, identity["username"], project_id, chat_id)

    # Call the AI handler turn using project parameters
    result = await ai_handler.handle_turn(
        source_platform="web",
        platform_user_id=str(identity["nebula_user_id"]),
        display_name=identity["display_name"],
        message_text=body.input,
        chat_id=None,  # Not SQL-backed, so we bypass normal chat_id
        search_mode=body.tools.search,
        model=body.model,
        project_id=project_id,  # Project context integration
        project_chat_id=chat_id, # Project chat ID
    )

    if result.is_blocked:
        is_coin_block = "coins" in result.blocked_reason.lower()
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED if is_coin_block else status.HTTP_403_FORBIDDEN,
            detail=result.blocked_reason,
        )

    # Re-fetch the updated chat data from disk to return the latest token usage/capacity
    chat_data = _map_exceptions(store.get_chat, identity["username"], project_id, chat_id)
    total_tokens = sum(m.get('token_count', 0) for m in chat_data["messages"])
    percentage = (total_tokens / memory.MAX_TOKENS) * 100 if memory.MAX_TOKENS else 0
    usage = {
        'total_tokens': total_tokens,
        'max_tokens': memory.MAX_TOKENS,
        'percentage': round(percentage, 2),
        'remaining': max(0, memory.MAX_TOKENS - total_tokens),
        'is_full': total_tokens >= memory.MAX_TOKENS,
    }

    return ProjectSendMessageResponse(
        reply_text=result.reply_text,
        tool_messages=result.tool_messages,
        memory_warning=result.memory_warning,
        usage=usage,
    )
