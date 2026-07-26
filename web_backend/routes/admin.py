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
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, status

from core.auth import AuthManager
from core.database import DatabaseManager
from core.coins import CoinManager
from web_backend.dependencies import get_auth, get_db, get_coin_manager, require_admin_identity_web
from web_backend.schemas.admin import (
    PendingUser,
    PendingUsersResponse,
    PlatformInfo,
    PlatformsResponse,
    ReviewUserRequest,
    ReviewUserResponse,
    UserRoleUpdate,
    UserUsageResponse,
    RoleSettingItem,
    RoleSettingsListResponse,
    RoleSettingsUpdateRequest,
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


@router.patch("/users/{user_id}/role", response_model=UserUsageResponse)
async def update_user_role(
    user_id: int,
    body: UserRoleUpdate,
    admin_identity: dict = Depends(require_admin_identity_web),
    db: DatabaseManager = Depends(get_db),
    coin_manager: CoinManager = Depends(get_coin_manager),
):
    target = db.get_user_by_id(user_id)
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No Nebula account found with that id.")

    unlimited_expires_at = None
    unlimited_mode = body.unlimited_mode
    if body.role == 'Researcher':
        if body.unlimited_mode == 'temporary':
            if body.unlimited_duration == '1 day':
                unlimited_expires_at = (datetime.utcnow() + timedelta(days=1)).strftime('%Y-%m-%d %H:%M:%S')
            elif body.unlimited_duration == '1 week':
                unlimited_expires_at = (datetime.utcnow() + timedelta(days=7)).strftime('%Y-%m-%d %H:%M:%S')
            elif body.unlimited_duration == '1 month':
                unlimited_expires_at = (datetime.utcnow() + timedelta(days=30)).strftime('%Y-%m-%d %H:%M:%S')
            elif body.unlimited_duration == 'indefinite':
                unlimited_mode = 'permanent'
                unlimited_expires_at = None
            else:
                unlimited_mode = 'none'
        elif body.unlimited_mode == 'permanent':
            unlimited_expires_at = None
        else:
            unlimited_mode = 'none'
    else:
        unlimited_mode = 'none'

    db.set_user_role(user_id, body.role, unlimited_mode, unlimited_expires_at)

    db.log_admin_action(
        admin_identity['nebula_user_id'], admin_identity['display_name'],
        "update_user_role", user_id, target['display_name'],
        f"role={body.role}, unlimited_mode={unlimited_mode}, expires={unlimited_expires_at}"
    )

    usage_info = coin_manager.get_status(user_id)
    return UserUsageResponse(
        nebula_user_id=user_id,
        daily_usage=usage_info['daily_usage'],
        weekly_usage=usage_info['weekly_usage'],
        daily_limit=usage_info['daily_limit'],
        weekly_limit=usage_info['weekly_limit'],
        role=usage_info['role'],
        unlimited_mode=usage_info['unlimited_mode'],
        unlimited_expires_at=usage_info['unlimited_expires_at']
    )


@router.get("/roles/settings", response_model=RoleSettingsListResponse)
async def get_all_roles_settings(
    admin_identity: dict = Depends(require_admin_identity_web),
    db: DatabaseManager = Depends(get_db),
):
    settings = db.get_all_role_settings()
    return RoleSettingsListResponse(settings=[
        RoleSettingItem(
            role=s['role'],
            allowed_models=s['allowed_models'],
            allowed_tools=s['allowed_tools'],
            daily_limit=s['daily_limit'],
            weekly_limit=s['weekly_limit']
        )
        for s in settings
    ])


@router.put("/roles/settings", response_model=RoleSettingItem)
async def update_role_settings_route(
    body: RoleSettingsUpdateRequest,
    admin_identity: dict = Depends(require_admin_identity_web),
    db: DatabaseManager = Depends(get_db),
):
    db.update_role_settings(
        body.role,
        body.allowed_models,
        body.allowed_tools,
        body.daily_limit,
        body.weekly_limit
    )
    settings = db.get_role_settings(body.role)
    return RoleSettingItem(
        role=settings['role'],
        allowed_models=settings['allowed_models'],
        allowed_tools=settings['allowed_tools'],
        daily_limit=settings['daily_limit'],
        weekly_limit=settings['weekly_limit']
    )


@router.get("/users/{user_id}/usage", response_model=UserUsageResponse)
async def get_any_user_usage(
    user_id: int,
    admin_identity: dict = Depends(require_admin_identity_web),
    db: DatabaseManager = Depends(get_db),
    coin_manager: CoinManager = Depends(get_coin_manager),
):
    target = db.get_user_by_id(user_id)
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No Nebula account found with that id.")

    usage_info = coin_manager.get_status(user_id)
    return UserUsageResponse(
        nebula_user_id=user_id,
        daily_usage=usage_info['daily_usage'],
        weekly_usage=usage_info['weekly_usage'],
        daily_limit=usage_info['daily_limit'],
        weekly_limit=usage_info['weekly_limit'],
        role=usage_info['role'],
        unlimited_mode=usage_info['unlimited_mode'],
        unlimited_expires_at=usage_info['unlimited_expires_at']
    )
