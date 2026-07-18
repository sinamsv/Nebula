"""GET /admin/users/pending, POST /admin/users/{id}/review,
GET /admin/platforms.

Confirmed with Sina: review is ONE combined endpoint taking
{"status": "approved" | "rejected"} in the body, targeting a
nebula_user_id in the path -- not two separate approve/reject
endpoints, and not username-based the way Discord's /approve_user
command is. See core/auth.py's AuthManager.approve_user_by_id() (new
method added alongside the existing username-based approve_user(),
which Discord/Telegram keep using unchanged) for why an id-based
variant was added rather than reusing approve_user() directly.
"""
from fastapi import APIRouter, Depends

from core.auth import AuthManager
from web_backend.dependencies import get_auth, require_admin_identity_web
from web_backend.schemas.admin import (
    PendingUser,
    PendingUsersResponse,
    PlatformInfo,
    PlatformsResponse,
    ReviewUserRequest,
    ReviewUserResponse,
)

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])

# Same static list philosophy as web_backend/routes/sync.py's
# _LINKABLE_PLATFORMS, but this is the ADMIN-facing "what platforms
# does this Nebula deployment support at all" list (confirmed as its
# own separate GET /admin/platforms in the spec, distinct from the
# public GET /platforms used for linking) -- kept as a second static
# list rather than reusing sync.py's, since the design doc treats them
# as two distinct confirmed endpoints and an admin-facing list may
# reasonably grow richer metadata (e.g. moderation capability, active
# user counts) independent of what the public linking list exposes.
_ADMIN_PLATFORMS = [
    PlatformInfo(id="discord", name="Discord", supports_guild_moderation=True),
    PlatformInfo(id="telegram", name="Telegram", supports_guild_moderation=False),
    PlatformInfo(id="web", name="Web", supports_guild_moderation=False),
]


@router.get("/users/pending", response_model=PendingUsersResponse)
async def list_pending_users(
    admin_identity: dict = Depends(require_admin_identity_web),
    auth: AuthManager = Depends(get_auth),
):
    pending = auth.list_pending(limit=100)
    return PendingUsersResponse(pending=[
        PendingUser(nebula_user_id=p['nebula_user_id'], username=p['username'],
                    display_name=p['display_name'], created_at=str(p['created_at']))
        for p in pending
    ])


@router.post("/users/{user_id}/review", response_model=ReviewUserResponse)
async def review_user(
    user_id: int,
    body: ReviewUserRequest,
    admin_identity: dict = Depends(require_admin_identity_web),
    auth: AuthManager = Depends(get_auth),
):
    from core.auth import AuthError
    from fastapi import HTTPException, status as http_status

    approve = body.status == "approved"
    try:
        result = auth.approve_user_by_id(
            target_nebula_user_id=user_id, approve=approve,
            approver_nebula_user_id=admin_identity['nebula_user_id'],
            approver_display_name=admin_identity['display_name'],
        )
    except AuthError as e:
        raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail=str(e))

    return ReviewUserResponse(
        nebula_user_id=result['nebula_user_id'], username=result['username'], approved=result['approved']
    )


@router.get("/platforms", response_model=PlatformsResponse)
async def admin_list_platforms(admin_identity: dict = Depends(require_admin_identity_web)):
    return PlatformsResponse(platforms=_ADMIN_PLATFORMS)
