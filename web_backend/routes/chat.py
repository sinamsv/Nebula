"""GET/POST /chat, GET /chat/{id}, POST /chat/{id}/messages,
POST /chat/{id}/messages/image, PATCH /chat/{id}, DELETE /chat/{id}.

Confirmed with Sina: there is NO separate /ai/generate endpoint for
web. GET /chat/{id} only returns history; POST /chat/{id}/messages is
what actually sends a message and gets a reply -- everything web-chat-
related lives under this one sub-resource. Also confirmed: the image
endpoint stays SEPARATE from the text endpoint
(/chat/{id}/messages/image vs /chat/{id}/messages), rather than one
endpoint branching on multipart vs JSON.

Every route here requires an APPROVED web identity (require_approved_identity_web)
and always calls AIHandler.handle_turn() with source_platform="web",
platform_user_id=str(nebula_user_id) (see web_backend/dependencies.py's
WEB_PLATFORM convention), discord_guild=None (so moderation tools are
never offered on web, same as Telegram), and a real chat_id -- this is
what makes each web chat get its own independent 200k-token cap (see
core/memory.py's docstring) rather than sharing the account-wide
Discord/Telegram cap.
"""
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

from ai.handler import AIHandler
from ai.providers.base import ImageAttachment
from core.database import DatabaseManager
from core.memory import MemoryManager
from web_backend.dependencies import (
    WEB_PLATFORM,
    get_ai_handler,
    get_db,
    get_memory,
    require_approved_identity_web,
)
from web_backend.schemas.chat import (
    ChatHistoryResponse,
    ChatListResponse,
    ChatMessage,
    ChatSummary,
    CreateChatRequest,
    RenameChatRequest,
    SendMessageRequest,
    SendMessageResponse,
)

router = APIRouter(prefix="/api/v1/chat", tags=["chat"])

# Mirrors ai/providers/base.py's ImageAttachment.mime_type docstring:
# the closed set Anthropic's SDK enumerates, which OpenAI/Google also
# both accept -- rejecting anything outside this set here (before any
# provider ever sees it) gives a clear 400 instead of an opaque
# provider-side error later.
_ALLOWED_IMAGE_MIME_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp"}
_MAX_IMAGE_BYTES = 10 * 1024 * 1024  # 10MB per image, generous for chat use, small enough to not abuse the API


def _require_owned_chat(db: DatabaseManager, chat_id: int, nebula_user_id: int) -> dict:
    chat = db.get_chat(chat_id)
    if chat is None or chat['nebula_user_id'] != nebula_user_id:
        # 404, not 403 -- deliberately don't reveal whether a chat_id
        # exists but belongs to someone else vs. doesn't exist at all.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat not found.")
    return chat


@router.get("", response_model=ChatListResponse)
async def list_chats(
    identity: dict = Depends(require_approved_identity_web),
    db: DatabaseManager = Depends(get_db),
):
    chats = db.list_chats(identity['nebula_user_id'])
    return ChatListResponse(chats=[
        ChatSummary(chat_id=c['chat_id'], title=c['title'],
                    created_at=str(c['created_at']), last_message_at=str(c['last_message_at']))
        for c in chats
    ])


@router.post("", response_model=ChatSummary, status_code=status.HTTP_201_CREATED)
async def create_chat(
    body: CreateChatRequest,
    identity: dict = Depends(require_approved_identity_web),
    db: DatabaseManager = Depends(get_db),
):
    chat_id = db.create_chat(identity['nebula_user_id'], title=body.title or "New Chat")
    chat = db.get_chat(chat_id)
    return ChatSummary(chat_id=chat['chat_id'], title=chat['title'],
                        created_at=str(chat['created_at']), last_message_at=str(chat['last_message_at']))


@router.get("/{chat_id}", response_model=ChatHistoryResponse)
async def get_chat_history(
    chat_id: int,
    identity: dict = Depends(require_approved_identity_web),
    db: DatabaseManager = Depends(get_db),
):
    chat = _require_owned_chat(db, chat_id, identity['nebula_user_id'])
    # limit=200 here (vs. the 50-message default AIHandler uses for
    # model context) is deliberate: this endpoint backs the UI's
    # scrollback view, which reasonably wants more history visible than
    # what's sent to the model on each turn for cost/context reasons.
    history = db.get_conversation_history(identity['nebula_user_id'], limit=200, chat_id=chat_id)
    return ChatHistoryResponse(
        chat_id=chat_id,
        title=chat['title'],
        messages=[
            ChatMessage(role=m['role'], content=m['content'],
                        source_platform=m['source_platform'], timestamp=str(m['timestamp']))
            for m in history
        ],
    )


@router.patch("/{chat_id}", response_model=ChatSummary)
async def rename_chat(
    chat_id: int,
    body: RenameChatRequest,
    identity: dict = Depends(require_approved_identity_web),
    db: DatabaseManager = Depends(get_db),
):
    _require_owned_chat(db, chat_id, identity['nebula_user_id'])
    db.rename_chat(chat_id, body.title)
    chat = db.get_chat(chat_id)
    return ChatSummary(chat_id=chat['chat_id'], title=chat['title'],
                        created_at=str(chat['created_at']), last_message_at=str(chat['last_message_at']))


@router.delete("/{chat_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_chat(
    chat_id: int,
    identity: dict = Depends(require_approved_identity_web),
    db: DatabaseManager = Depends(get_db),
):
    _require_owned_chat(db, chat_id, identity['nebula_user_id'])
    db.delete_chat(chat_id)


@router.post("/{chat_id}/messages", response_model=SendMessageResponse)
async def send_message(
    chat_id: int,
    body: SendMessageRequest,
    identity: dict = Depends(require_approved_identity_web),
    db: DatabaseManager = Depends(get_db),
    memory: MemoryManager = Depends(get_memory),
    ai_handler: AIHandler = Depends(get_ai_handler),
):
    _require_owned_chat(db, chat_id, identity['nebula_user_id'])
    return await _run_turn(
        identity, chat_id, body.input, ai_handler, memory,
        images=None, enable_search=body.tools.search,
    )


@router.post("/{chat_id}/messages/image", response_model=SendMessageResponse)
async def send_message_with_image(
    chat_id: int,
    text: str = "",
    image: UploadFile = File(...),
    identity: dict = Depends(require_approved_identity_web),
    db: DatabaseManager = Depends(get_db),
    memory: MemoryManager = Depends(get_memory),
    ai_handler: AIHandler = Depends(get_ai_handler),
):
    """Kept as a SEPARATE endpoint from send_message() above (confirmed
    with Sina), taking multipart/form-data rather than JSON since it
    carries a real file upload. text is an optional accompanying
    caption/question -- an empty string is valid (e.g. just "what is
    this?" implied by the image alone), matching how a chat UI's image-
    attach affordance typically works (attach first, optionally type
    a caption).

    This is a genuine capability upgrade over Discord/Telegram, which
    today only append a "[User attached N image(s)]" text placeholder
    (see discord_bot/message_listener.py's documented known gap) --
    confirmed as intentional: web does real multimodal forwarding."""
    _require_owned_chat(db, chat_id, identity['nebula_user_id'])

    if image.content_type not in _ALLOWED_IMAGE_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported image type '{image.content_type}'. Allowed: {', '.join(sorted(_ALLOWED_IMAGE_MIME_TYPES))}.",
        )

    image_bytes = await image.read()
    if len(image_bytes) > _MAX_IMAGE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Image too large. Max size is {_MAX_IMAGE_BYTES // (1024 * 1024)}MB.",
        )
    if len(image_bytes) == 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded image is empty.")

    attachment = ImageAttachment(data=image_bytes, mime_type=image.content_type)
    # A caption-less image still needs SOME message_text for handle_turn()
    # to store as the user's turn -- fall back to a neutral prompt
    # rather than storing an empty string as the user's memory entry.
    message_text = text.strip() if text and text.strip() else "[Image attached]"

    # Image messages always offer search too, same default as text
    # messages -- there's no separate tool-toggle body field on the
    # multipart image endpoint (confirmed shape carries only text +
    # image), so this uses the same enable_search=True default
    # send_message() uses when body.tools is left at its default.
    return await _run_turn(identity, chat_id, message_text, ai_handler, memory, images=[attachment], enable_search=True)


async def _run_turn(
    identity: dict,
    chat_id: int,
    message_text: str,
    ai_handler: AIHandler,
    memory: MemoryManager,
    images: Optional[list],
    enable_search: bool = True,
) -> SendMessageResponse:
    result = await ai_handler.handle_turn(
        source_platform=WEB_PLATFORM,
        platform_user_id=str(identity['nebula_user_id']),
        display_name=identity['display_name'],
        message_text=message_text,
        discord_guild=None,  # web never offers moderation tools, same as Telegram
        chat_id=chat_id,
        images=images,
        enable_search=enable_search,
    )

    if result.is_blocked:
        # 402 Payment Required for the coin case reads oddly literally
        # for a "Nebula Coin" (not real currency), but semantically it's
        # the closest standard status for "you don't have enough of a
        # metered resource" -- 403 is used for every other blocked
        # reason (unapproved, memory full, AI unconfigured) since those
        # are closer to "not permitted right now" than "payment needed".
        # This distinction is for API consumers/tooling; the frontend
        # reads `detail` either way.
        is_coin_block = "coins" in result.blocked_reason.lower()
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED if is_coin_block else status.HTTP_403_FORBIDDEN,
            detail=result.blocked_reason,
        )

    usage = memory.get_usage(identity['nebula_user_id'], chat_id=chat_id)
    return SendMessageResponse(
        reply_text=result.reply_text,
        tool_messages=result.tool_messages,
        memory_warning=result.memory_warning,
        usage=usage,
    )
