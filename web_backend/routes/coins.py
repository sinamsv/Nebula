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
from fastapi import APIRouter, Depends, HTTPException, status

from core.coins import CoinManager
from core.database import DatabaseManager
from web_backend.dependencies import (
    get_coin_manager,
    get_db,
    require_admin_identity_web,
    require_approved_identity_web,
)
from web_backend.schemas.admin import CoinStatusResponse, ModifyCoinsRequest, ModifyCoinsResponse

router = APIRouter(prefix="/api/v1/users", tags=["coins"])


@router.get("/me/coins", response_model=CoinStatusResponse)
async def get_my_coins(
    identity: dict = Depends(require_approved_identity_web),
    coin_manager: CoinManager = Depends(get_coin_manager),
):
    status_dict = coin_manager.get_status(identity['nebula_user_id'])
    return CoinStatusResponse(**status_dict)


@router.post("/{user_id}/coins", response_model=ModifyCoinsResponse)
async def modify_user_coins(
    user_id: int,
    body: ModifyCoinsRequest,
    admin_identity: dict = Depends(require_admin_identity_web),
    coin_manager: CoinManager = Depends(get_coin_manager),
    db: DatabaseManager = Depends(get_db),
):
    target = db.get_user_by_id(user_id)
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No Nebula account found with that id.")

    new_balance = coin_manager.modify_coins(user_id, body.amount, body.mode)

    db.log_admin_action(
        admin_identity['nebula_user_id'], admin_identity['display_name'],
        "add_coin", user_id, target['display_name'],
        f"mode={body.mode}, amount={body.amount}, new_balance={new_balance}",
    )

    return ModifyCoinsResponse(nebula_user_id=user_id, new_balance=new_balance)
