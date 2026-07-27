"""GET /users/me/coins, POST /users/{userID}/coins.

Confirmed with Sina: GET is self-only (/users/me/coins, not
/users/{userID}/coins) -- there's no admin "view someone else's
balance" read path on web for now (mirrors that Discord/Telegram also
have no equivalent read-someone-else's-balance command; the closest
existing thing, user_activity_check, is a broader admin report tool,
not a coins-specific getter). POST (admin-only, modify) DOES take a
path id, per the original spec, since granting/setting coins
necessarily targets someone else.
"""
from fastapi import APIRouter, Depends

from core.coins import CoinManager
from web_backend.dependencies import (
    get_coin_manager,
    require_approved_identity_web,
)
from web_backend.schemas.admin import CoinStatusResponse

router = APIRouter(prefix="/api/v1/users", tags=["coins"])


@router.get("/me/coins", response_model=CoinStatusResponse)
async def get_my_coins(
    identity: dict = Depends(require_approved_identity_web),
    coin_manager: CoinManager = Depends(get_coin_manager),
):
    status_dict = coin_manager.get_status(identity['nebula_user_id'])
    return CoinStatusResponse(**status_dict)
