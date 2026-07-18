"""POST /sync/{platform}, GET /platforms.

Confirmed with Sina: one-directional. Web only ISSUES sync codes
(mirroring Discord's existing /sync command) -- there is deliberately
NO web-side "consume a code" endpoint. A user who wants to link Discord
or Telegram to their web account generates a code here, then runs
/verify username:<u> code:<c> on that platform's bot, exactly the same
flow Discord -> Telegram already uses today (see core/auth.py's
verify_sync_code() and discord_bot/sync_commands.py's docstring for the
existing mechanics this reuses unchanged -- web is simply a THIRD
issuing platform alongside Discord, using the exact same
generate_sync_code()/platform_sync_codes plumbing, no schema or
core/auth.py changes needed for this part).

Platforms are hardcoded (confirmed with Sina) -- no platforms DB table,
no POST /admin/platforms.
"""
from fastapi import APIRouter, Depends, HTTPException, status

from core.auth import AuthManager, SYNC_CODE_EXPIRY_MINUTES
from web_backend.dependencies import get_auth, require_approved_identity_web
from web_backend.schemas.admin import PlatformInfo, PlatformsResponse
from web_backend.schemas.sync import SyncCodeResponse

router = APIRouter(prefix="/api/v1", tags=["sync"])

# Static, hardcoded platform metadata (confirmed with Sina -- no DB
# table backing this). "web" itself is deliberately excluded from the
# LINKABLE list returned by /platforms: you can't /sync FROM web TO
# web, and web is never a /verify-consuming target today (it already
# has its own signup/login/Google-OAuth paths for getting an account
# linked in the first place) -- this list is specifically "what can I
# link TO my account from here", matching the dashboard's "Platforms"
# panel description in the design doc.
_LINKABLE_PLATFORMS = [
    PlatformInfo(id="discord", name="Discord", supports_guild_moderation=True),
    PlatformInfo(id="telegram", name="Telegram", supports_guild_moderation=False),
]
_LINKABLE_PLATFORM_IDS = {p.id for p in _LINKABLE_PLATFORMS}


@router.get("/platforms", response_model=PlatformsResponse)
async def list_platforms():
    return PlatformsResponse(platforms=_LINKABLE_PLATFORMS)


@router.post("/sync/{platform}", response_model=SyncCodeResponse)
async def generate_sync_code(
    platform: str,
    identity: dict = Depends(require_approved_identity_web),
    auth: AuthManager = Depends(get_auth),
):
    if platform not in _LINKABLE_PLATFORM_IDS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown or unsupported target platform '{platform}'. Valid values: {', '.join(sorted(_LINKABLE_PLATFORM_IDS))}.",
        )

    code = auth.generate_sync_code(identity['nebula_user_id'], platform)

    return SyncCodeResponse(
        code=code,
        target_platform=platform,
        expiry_minutes=SYNC_CODE_EXPIRY_MINUTES,
        verify_command_hint=f"/verify username:{identity['username']} code:{code}",
    )
